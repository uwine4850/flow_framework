class FlowException(Exception):
    def __init__(self, msg='Flow error'):
        self.msg = msg

    def __str__(self):
        return self.msg


if __name__ == '__main__':
    raise FlowException()
