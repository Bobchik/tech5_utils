import os
import gspread
import string
import logging
from datetime import date, datetime


class GoogleSheets:
    def __init__(self, doc, sheet, header_row=1, last_data_row=None):
        # make sure the sheet is shared with developer@t5-local-test.iam.gserviceaccount.com
        # filepath = os.path.abspath(os.path.join(__file__, 'credentials_t5.json'))
        credentials_file = os.environ.get('GOOGLE_CREDENTIALS')
        filepath = os.path.join(os.path.dirname(__file__), credentials_file)
        gc = gspread.service_account(filename=filepath)
        self.doc_name = doc
        if doc.startswith('https://'):
            self.doc = gc.open_by_url(doc)
        else:
            self.doc = gc.open_by_key(doc)
        self.sheet_name = sheet
        self.sheet = self.doc.worksheet(sheet)
        self.headers = [self.slugify(e) for e in self.sheet.row_values(header_row)]
        self.first_data_row = header_row + 1
        self.last_data_row = last_data_row

    @staticmethod
    def slugify(key):
        return key.lower().strip().replace(' ', '_')

    def find_row(self, **kwargs):
        for key, value in kwargs.items():
            if key not in self.headers:
                raise ValueError(f"Wrong key {key}, should be one of {self.headers}")
            all_column = self.sheet.col_values(self.headers.index(key) + 1)
            if self.last_data_row:
                column_date = all_column[self.first_data_row - 1:self.last_data_row - 1]
            else:
                column_date = all_column[self.first_data_row - 1:]
            if value in column_date:
                return column_date.index(value)
        else:
            raise ValueError(f"Row with {key}={value} was not found")

    def get_row_dict(self, row_n):
        return self.get_range_dicts(row_n, row_n)[0]

    def find_row_dict(self, **kwargs):
        """Shortcut to find and return row as dictionary. Row index will be still needed for updates."""
        row_n = self.find_row(**kwargs)
        return self.get_row_dict(row_n)

    def update_row(self, index, **kwargs):
        row = index + self.first_data_row
        if self.last_data_row and row > self.last_data_row:
            raise ValueError(f'Row {index} is outside of editable section: last row is {self.last_data_row}')

        slug_headers = [self.slugify(k) for k in self.headers]
        for key, value in kwargs.items():
            if key not in slug_headers:
                raise ValueError('Key %s is missing in headers' % key)
            col = slug_headers.index(key) + 1
            self.sheet.update_cell(row, col, value)
        # self.sheet.values_append(self.sheet, {'valueInputOption': 'USER_ENTERED'}, {'values': put_values})

    def get_range_dicts(self, first_row=0, last_row=None, row_amount=None):
        # if not first_row:
        #     first_row = self.first_data_row
        first_row_absolute = first_row + self.first_data_row - 1
        all_values = self.sheet.get_all_values()
        if last_row:
            last_row_absolute = last_row + self.first_data_row
            list_of_lists = all_values[first_row_absolute:last_row_absolute]
        elif row_amount:
            list_of_lists = all_values[first_row_absolute:first_row_absolute + row_amount]
        else:
            list_of_lists = all_values[first_row_absolute:]
        # cast to dicts
        list_of_dicts = []
        for row in list_of_lists:
            row_dict = {}
            for i, key in enumerate(self.headers):
                if not key:
                    continue
                row_dict[key] = row[i]
            list_of_dicts.append(row_dict)
        return list_of_dicts


class GoogleSheetSection(GoogleSheets):
    def __init__(self, doc, sheet, section_name):
        super().__init__(doc, sheet, header_row=1)
        all_values = self.sheet.get_all_values()
        all_values_filtered = [list(filter(bool, v)) for v in all_values]
        header_row = None
        last_data_row = None
        for i, row in enumerate(all_values_filtered, 1):
            if row == [section_name]:
                header_row = i + 1
            # if header_row is found, detect empty row and end of section
            if header_row and row == []:
                last_data_row = i
                break
        if not header_row:
            raise ValueError(f"Section {section_name} not found in {sheet}")
        # we initialize same class again, giving the header row of section
        super().__init__(doc, sheet, header_row=header_row, last_data_row=last_data_row)


class GoogleYearlyHoursSection(GoogleSheetSection):
    def __init__(self, doc, month, customer):
        self.month = month
        sheet_name = month.strftime("%Y_hours")
        super().__init__(doc, sheet_name, section_name=customer)

    def set_monthly_hours(self, employee, hours):
        row_n = self.find_row(employee=employee)
        update_dict = {self.month.strftime("%B").lower(): hours}
        self.update_row(row_n, **update_dict)


class GoogleDailyTimeSheets(GoogleSheets):
    def __init__(self, doc, sheet):
        """TimeSheets have the data table starting at row 5"""
        super().__init__(doc, sheet, header_row=5)

    @classmethod
    def parse_duration(cls, duration):
        """Assumes duration is either hours in float, or a string like 02:20"""
        if not duration:
            return 0
        if not isinstance(duration, str):
            duration = str(duration)
        if ':' not in duration:
            duration = float(duration)
            if duration > 24:
                raise ValueError(f"Hour duration {duration} is over 24, check format")
            duration = cls.format_duration(hours=duration)
        duration_minutes = int(duration[:-3]) * 60 + int(duration[-2:])
        return duration_minutes

    @classmethod
    def format_duration(cls, hours: float = 0, minutes: float = 0):
        if hours:
            minutes += hours * 60
        duration = '{0:02.0f}:{1:02.0f}'.format(*divmod(minutes, 60))
        return duration


    def get_all_days_dicts(self, skip_empty=True, parse_hours=True):
        rows = self.get_range_dicts(row_amount=31)
        if skip_empty:
            rows = [row for row in rows if row.get('daily_hours')]
        if parse_hours:
            for row in rows:
                row['duration_minutes'] = self.parse_duration(row['daily_hours'])
        return rows

    def get_days_in_range(self, start: datetime, end: datetime):
        months = month_year_iter(start.month, start.year, end.month, end.year)
        rows_total = []
        for year, month in months:
            dt = date(day=1, month=month, year=year)
            sheet_name = dt.strftime('%b %y')
            # month located on current sheet
            if sheet_name == self.sheet_name:
                rows = self.get_all_days_dicts()
            # need to open another sheet
            else:
                temp_sheet = GoogleDailyTimeSheets(self.doc_name, sheet_name)
                rows = temp_sheet.get_all_days_dicts()
            rows_total.extend(rows)
        # filter resulting range by start and end
        rows_filtered = []
        for row in rows_total:
            dt = datetime.strptime(row['date'], '%d %b %Y')
            if not start <= dt <= end:
                continue
            row['date_dt'] = dt
            rows_filtered.append(row)
        rows_filtered.sort(key=lambda x: x['date_dt'])
        return rows_filtered


class GoogleTransactionSheets(GoogleSheets):

    def write_transactions(self, transactions):
        rows = []
        for tr in transactions:
            row = []
            for header in self.headers:
                # try to avoid overriding
                value = tr.meta.get(header)
                row.append(value)
            rows.append(row)
        row_start = 'A%s' % self.first_data_row
        end_letter = (string.ascii_lowercase[len(self.headers)-1]).upper()
        end_number = len(rows) + self.first_data_row - 1
        row_end = '%s%s' % (end_letter, end_number)
        self.sheet.update(f"{row_start}:{row_end}", rows)


    def sync_transactions(self, transactions):
        list_of_dicts = self.sheet.get_all_records()
        for t in transactions:
            if 'privat' in t.meta['message']:
                logging.info("Please book this transaction as private and start over")
                breakpoint()
            # if not t.meta.get('supplier') and float(t.amount) < 0:
            #     print('- Purpose:')
            #     print(t.meta['message'])
            #     print('- Amount:')
            #     print(t.amount)
            #     print('='*80, '\n')
        if not list_of_dicts:
           self.write_transactions(transactions)
        for tr, row in zip(transactions, list_of_dicts):
            # check if rows match
            if tr.meta.get('id') and str(row['id']) != str(tr.id):
                breakpoint()
                raise ValueError("Rows dont match: %s" % row)
            elif tr.meta.get('status') == 'booked' and row['Status'] != 'booked':
                # transaction was booked meanwhile
                i = transactions.index(tr)
                self.update_row(i, status="booked")
            # update order details: link and supplier name
            if tr.meta.get('link') and tr.meta['link'] != row['Link']:
                i = transactions.index(tr)
                self.update_row(i, link=tr.meta.get('link'))

            if tr.meta.get('supplier') and tr.meta['supplier'] != row['Supplier']:
                i = transactions.index(tr)
                self.update_row(i, supplier=tr.meta.get('supplier'))

            tr.meta['status'] = row['Status']

    def highlight(self, row, color='green'):
        i = self.first_data_row + row
        color_dict = {
            "green": {
                "red": 0.6,
                "green": 0.9,
                "blue": 0.6,
            },
            "ltgreen": {
                "red": 0.9,
                "green": 0.99,
                "blue": 0.9,
            },
            "ltgray": {
                "red": 0.9,
                "green": 0.9,
                "blue": 0.9,
            },
            "red": {
                "red": 0.9,
                "green": 0.6,
                "blue": 0.6,
            },

        }
        self.sheet.format(f"A{i}:J{i}", {
            "backgroundColor": color_dict[color]
            # "horizontalAlignment": "CENTER",
            # "textFormat": {
            # "foregroundColor": {
            #     "red": 1.0,
            #     "green": 1.0,
            #     "blue": 1.0
            # },
            # "fontSize": 12,
            # "bold": True
            # }
    })

    def unhighlight(self, row):
        if row < 0:
            return
        i = self.first_data_row + row
        self.sheet.format(f"A{i}:J{i}", {
            "backgroundColor": {
                "red": 1,
                "green": 1,
                "blue": 1,
            },
        })


def month_year_iter(start_month, start_year, end_month, end_year):
    ym_start = 12 * start_year + start_month - 1
    ym_end = 12 * end_year + end_month
    for ym in range(ym_start, ym_end):
        y, m = divmod(ym, 12)
        yield y, m + 1
