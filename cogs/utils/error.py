import os
import prettify_exceptions

class OpenRobotFormatter(prettify_exceptions.DefaultFormatter):
    def __init__(self, **kwargs):
        kwargs['theme'] = {'_ansi_enabled': True if (not os.environ.get('OPENROBOT-FORMATTER_NO_COLOR', 'True').lower() == 'true') or (not kwargs.pop('no_color', True)) else False}

        super().__init__(**kwargs)