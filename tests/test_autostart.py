from contextlib import nullcontext
import unittest
from app.services.autostart import Autostart, startup_command, VALUE_NAME


class FakeRegistry:
    HKEY_CURRENT_USER = 1
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1
    def __init__(self):
        self.values = {'OtherApp':'keep'}
        self.writes = 0
    def OpenKey(self,*args):
        return nullcontext('key')
    def CreateKeyEx(self,*args):
        return nullcontext('key')
    def QueryValueEx(self,key,name):
        if name not in self.values:
            raise FileNotFoundError()
        return self.values[name],self.REG_SZ
    def SetValueEx(self,key,name,reserved,kind,value):
        self.writes += 1
        self.values[name] = value
    def DeleteValue(self,key,name):
        self.writes += 1
        del self.values[name]


class AutostartTests(unittest.TestCase):
    def test_default_and_read_never_write(self):
        registry = FakeRegistry()
        service = Autostart(registry)
        self.assertIsNone(service.current_command())
        service.set_enabled(False)
        self.assertEqual(registry.writes,0)

    def test_enable_disable_only_own_value(self):
        registry = FakeRegistry()
        service = Autostart(registry)
        service.set_enabled(True)
        self.assertIn('--autostart',registry.values[VALUE_NAME])
        service.set_enabled(False)
        self.assertNotIn(VALUE_NAME,registry.values)
        self.assertEqual(registry.values['OtherApp'],'keep')

    def test_command_quotes_spaces_and_frozen(self):
        text = startup_command(r'C:\Program Files\Python\python.exe',r'E:\My Class\main.py',False)
        self.assertIn('"E:\\My Class\\main.py"',text)
        self.assertIn('"C:\\Program Files\\Python\\python.exe"',text)
        self.assertEqual(startup_command(r'E:\My Class\ClassWidget.exe',frozen=True),'"E:\\My Class\\ClassWidget.exe" --autostart')

    def test_long_command_rejected(self):
        with self.assertRaises(ValueError):
            startup_command('C:\\'+'x'*280+'\\app.exe',frozen=True)
