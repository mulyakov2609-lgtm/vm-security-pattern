import unittest
from unittest.mock import patch, mock_open
import app

class CoreTests(unittest.TestCase):
    def setUp(self):
        app.HITS.clear()
    def test_rate_window(self):
        self.assertEqual([app.check_rate("gateway-ingress",1) for _ in range(8)], [True]*5+[False]*3)
        self.assertTrue(app.check_rate("gateway-ingress",12))
    def test_policy(self):
        self.assertTrue(app.check_file_policy("read","/protected/demo.txt")[0])
        for op,path in [("write","/protected/demo.txt"),("mount","/shared"),("execute","/shared/x"),("read","/protected/../etc/passwd"),("read",None)]:
            self.assertFalse(app.check_file_policy(op,path)[0])
    def test_data(self):
        self.assertEqual(app.get_data("/data")[0],200)
        self.assertEqual(app.get_data("/wrong")[0],404)
        with patch("builtins.open",mock_open(read_data="demo")):
            self.assertEqual(app.get_data("/file"),(200,{"content":"demo"}))
    def test_policy_failure(self):
        with patch.object(app,"call",return_value=(503,{})),patch.object(app,"audit"):
            self.assertEqual(app.handle_file_operation("read","/protected/demo.txt")[0],503)
    def test_allowed_file_internal_data(self):
        with patch.object(app,"call",side_effect=[(200,{"allowed":True}),(200,{"content":"demo"})]) as sender:
            self.assertEqual(app.handle_file_operation("read","/protected/demo.txt")[0],200)
            self.assertEqual(sender.call_args.args,("data","/file"))
    def test_invalid_service(self):
        self.assertEqual(app.call("external-host","/data")[0],400)

if __name__ == "__main__":
    unittest.main()
