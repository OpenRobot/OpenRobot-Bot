import re
import typing

class TagItem:
    def __init__(self, data):
        # Just for the purpose of linters and AttributeErrors:
        self.id = None
        self.name = None
        self.owner_id = None
        self.uses = None
        self.can_delete = None
        self.is_alias = None

        for key, value in data.items():
            setattr(self, key, value)

class Tags:
    def __init__(self, data: list[dict[str, typing.Any]]):
        self.data = data

    @classmethod
    def parse(cls, string: str):
        raw_rows = string.split('\n')
        rows = []

        # Strip all items in list
        for raw_row in raw_rows:
            if raw_row.strip():
                rows.append(raw_row.strip())

        # Get the column names:
        raw_columns = raw_rows[1].split('|')
        columns = []

        # Strip all items in list
        for raw_column in raw_columns:
            if raw_column.strip():
                columns.append(raw_column.strip())

        data = []

        # Get the data

        for row in rows[3:]:
            try:
                raw_data_columns = row[1].split('|')
                data_columns = []

                # Strip all items in list
                for raw_data_column in raw_data_columns:
                    if raw_data_column.strip():
                        data_columns.append(raw_data_column.strip())

                if len(columns) != len(data_columns):
                    #raise ValueError(f"Columns and data columns do not match up.")
                    continue

                if len(columns) < len(data_columns):
                    data.append({
                        (columns[i]): data_columns[i] for i in range(len(columns))
                    })
                else:
                    data.append({
                        (columns[i]): data_columns[i] for i in range(len(data_columns))
                    })
            except Exception as e:
                raise e

        return cls(data)

    def __iter__(self):
        return iter(self.items)

    def __next__(self):
        return next(self.__iter__())

    @property
    def items(self):
        return [TagItem(item) for item in self.data]

    def get(self, **kwargs) -> TagItem | None:
        for row in self.data:
            if all(row[key] == value for key, value in kwargs.items()):
                return TagItem(row)

        return None

    def get_all(self, **kwargs) -> list[TagItem]:
        return [TagItem(row) for row in self.data if all(row[key] == value for key, value in kwargs.items())]