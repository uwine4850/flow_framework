from flow.exceptions.base import FlowException


class ErrorWritingToFile(FlowException):
    def __init__(self, msg: str = None, filepath=None):
        if not msg:
            if filepath:
                self.msg = f"An error occurred while trying to write data to file '{filepath}'."
            else:
                self.msg = "An error occurred while trying to write data."
        else:
            self.msg = msg
        super().__init__(self.msg)


class ErrorAddingTableToLog(FlowException):
    def __init__(self, msg: str = None, tablename=None):
        if not msg:
            if tablename:
                self.msg = f"Error adding table '{tablename}' to log database."
            else:
                self.msg = "Error adding table to log database."
        else:
            self.msg = msg
        super().__init__(self.msg)


class ErrorAddingFieldToLog(FlowException):
    def __init__(self, msg: str = None, fname=None):
        if not msg:
            if fname:
                self.msg = f"Error adding field '{fname}' to log database."
            else:
                self.msg = "Error adding field to log database."
        else:
            self.msg = msg
        super().__init__(self.msg)


class ErrorUpdateFieldInLog(FlowException):
    def __init__(self, msg: str = None, fname=None):
        if not msg:
            if fname:
                self.msg = f"Error updating field '{fname}' in log."
            else:
                self.msg = "Error while updating the field in the log."
        else:
            self.msg = msg
        super().__init__(self.msg)


class ErrorDeleteFieldInLog(FlowException):
    def __init__(self, msg: str = None, fname=None):
        if not msg:
            if fname:
                self.msg = f"Error deleting field '{fname}' in log."
            else:
                self.msg = "Error while deleting the field in the log."
        else:
            self.msg = msg
        super().__init__(self.msg)


class ErrorDeleteTableInLog(FlowException):
    def __init__(self, msg: str = None, tn=None):
        if not msg:
            if tn:
                self.msg = f"Error deleting table '{tn}' in log."
            else:
                self.msg = "Error while deleting the table in the log."
        else:
            self.msg = msg
        super().__init__(self.msg)


class ErrorValidation(FlowException):
    def __init__(self, msg: str = None):
        if msg:
            self.msg = msg
        else:
            self.msg = 'Validation error.'
        super().__init__(self.msg)


class CreationError(FlowException):
    def __init__(self, msg: str = None):
        if msg:
            self.msg = msg
        else:
            self.msg = 'Creation error.'
        super().__init__(self.msg)


class ApplyValidationError(FlowException):
    def __init__(self, msg: str = None):
        if msg:
            self.msg = msg
        else:
            self.msg = 'Apply validation error.'
        super().__init__(self.msg)
