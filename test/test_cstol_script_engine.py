# Copyright 2025 OpenC3, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
#
# CSTOL language originally developed by the University of Colorado / LASP.

import pytest
import datetime
import unittest.mock as mock
from unittest.mock import MagicMock
from cstol_script_engine import CstolScriptEngine, CstolVariables
from openc3.script.exceptions import CheckError, StopScript

class TestCstolVariables:
    def test_init(self):
        variables = CstolVariables()
        assert variables.local_variables == {}
        assert variables.loop_stack == []
        assert "$$OWLT" in variables.special_variables
        assert "$$ERROR" in variables.special_variables

    def test_set_special_variable(self):
        variables = CstolVariables()
        variables.set_special_variable("$$TEST", 42)
        assert variables.special_variables["$$TEST"] == 42

    def test_set_special_variable_invalid_name(self):
        variables = CstolVariables()
        with pytest.raises(ValueError, match="Special variable names must start with"):
            variables.set_special_variable("TEST", 42)

    def test_get_special_variable(self):
        variables = CstolVariables()
        assert variables.get_special_variable("$$OWLT") == 0.0
        assert variables.get_special_variable("$$ERROR") == "NO_ERROR"
        assert variables.get_special_variable("$$LOOP_COUNT") == 0
        variables.loop_stack.append([10, 3, 4])
        assert variables.get_special_variable("$$LOOP_COUNT") == 4

    def test_get_special_variable_invalid_name(self):
        variables = CstolVariables()
        with pytest.raises(ValueError, match="Special variable names must start with"):
            variables.get_special_variable("TEST")


class TestCstolScriptEngine:
    def setup_method(self):
        self.mock_running_script = MagicMock()
        self.engine = CstolScriptEngine(self.mock_running_script)

    def test_init(self):
        assert isinstance(self.engine.variables, CstolVariables)

    def test_cstol_tokenizer_reconstructs_timestamps(self):
        result = self.engine.cstol_tokenizer('WRITE 11:30:00')
        assert result == ['WRITE', '11:30:00']
        result = self.engine.cstol_tokenizer('WRITE 2025/123-11:30:00.57')
        assert result == ['WRITE', '2025/123-11:30:00.57']
        result = self.engine.cstol_tokenizer('WRITE /123-11:30:00.57')
        assert result == ['WRITE', '/123-11:30:00.57']
        result = self.engine.cstol_tokenizer('WRITE 2025/-11:30:00.57')
        assert result == ['WRITE', '2025/-11:30:00.57']
        result = self.engine.cstol_tokenizer('WRITE /-11:30:00.57')
        assert result == ['WRITE', '/-11:30:00.57']

    def test_cstol_tokenizer_preserves_other_tokens(self):
        # Test that non-timestamp tokens are preserved
        result = self.engine.cstol_tokenizer('WRITE "Hello" , "World"')
        assert result == ['WRITE', '"Hello"', ',', '"World"']

    def test_cstol_tokenizer_multiple_timestamps(self):
        # Test with multiple timestamps in one line
        result = self.engine.cstol_tokenizer('WAIT 2025/100-10:00:00 OR 2025/101-11:00:00')
        assert result == ['WAIT', '2025/100-10:00:00', 'OR', '2025/101-11:00:00']

    def test_cstol_tokenizer_edge_cases(self):
        # Test that incomplete timestamp patterns are not reconstructed
        result = self.engine.cstol_tokenizer('WRITE 2025/123')
        assert result == ['WRITE', '2025', '/', '123']

        # Test with fractional seconds
        result = self.engine.cstol_tokenizer('WAIT 2024/001-00:00:00.123456')
        assert result == ['WAIT', '2024/001-00:00:00.123456']

    def test_parse_timestamp_basic(self):
        result = self.engine.parse_timestamp("12:34:56")
        assert result == 45296.0

    def test_parse_timestamp_with_year(self):
        result = self.engine.parse_timestamp("2025/1-12:34:56")
        assert result == 1735734896.0

    def test_parse_timestamp_without_year(self):
        now = datetime.datetime(2025, 1, 1, 0, 0, 0)
        result = self.engine.parse_timestamp("/-12:34:56", now)
        assert result == 1735734896.0

    def test_parse_timestamp_with_year(self):
        now = datetime.datetime(2025, 1, 1, 0, 0, 0)
        result = self.engine.parse_timestamp("2025/-12:34:56", now)
        assert result == 1735734896.0

    def test_handle_declare_variable(self):
        tokens = ["DECLARE", "VARIABLE", "$TEST", "=", "42"]
        self.engine.handle_declare(tokens, 1)
        assert self.engine.variables.local_variables["$TEST"] == 42

    def test_handle_declare_invalid_mode(self):
        tokens = ["DECLARE", "INVALID", "$TEST", "=", "42"]
        with pytest.raises(ValueError, match="Invalid mode"):
            self.engine.handle_declare(tokens, 1)

    def test_handle_declare_invalid_variable_name(self):
        tokens = ["DECLARE", "VARIABLE", "TEST", "=", "42"]
        with pytest.raises(ValueError, match="Variable name must start with"):
            self.engine.handle_declare(tokens, 1)

    def test_handle_loop_infinite(self):
        tokens = ["LOOP"]
        result = self.engine.handle_loop(tokens, 5)
        assert result == 6
        assert len(self.engine.variables.loop_stack) == 1
        assert self.engine.variables.loop_stack[0] == [6, None, 1]

    def test_handle_loop_counted(self):
        tokens = ["LOOP", "5"]
        result = self.engine.handle_loop(tokens, 10)
        assert result == 11
        assert len(self.engine.variables.loop_stack) == 1
        assert self.engine.variables.loop_stack[0] == [11, 5, 1]

    def test_extract_expressions_comma_separator(self):
        tokens = ["A", ",", "B", ",", "C"]
        result = self.engine.extract_expressions(tokens, ",")
        assert result == [["A"], ["B"], ["C"]]

    def test_extract_expressions_to_separator(self):
        tokens = ["VALUE", "TO", "TARGET"]
        result = self.engine.extract_expressions(tokens, "TO")
        assert result == [["VALUE"], ["TARGET"]]

    @mock.patch('cstol_script_engine.ask_string')
    def test_handle_ask(self, mock_ask_string):
        mock_ask_string.return_value = "test_answer"
        tokens = ["ASK", "$VAR", "What is your name?"]
        self.engine.handle_ask(tokens, 1)
        mock_ask_string.assert_called_once_with("What is your name?")
        assert self.engine.variables.local_variables["$VAR"] == "TEST_ANSWER"

    @mock.patch('cstol_script_engine.ask_string')
    def test_handle_ask_quoted(self, mock_ask_string):
        mock_ask_string.return_value = "\"tesT_Answer\""
        tokens = ["ASK", "$VAR", "\"What is your name?\""]
        self.engine.handle_ask(tokens, 1)
        mock_ask_string.assert_called_once_with("What is your name?")
        assert self.engine.variables.local_variables["$VAR"] == "tesT_Answer"

    def test_handle_ask_invalid_format(self):
        tokens = ["ASK", "$VAR"]
        with pytest.raises(ValueError, match="Invalid ASK command format"):
            self.engine.handle_ask(tokens, 1)

    def test_handle_return(self):
        lines = ["IF 1 = 1", "  RETURN", "ENDIF"]
        tokens = ["RETURN"]
        result = self.engine.handle_return(tokens, lines, 2)
        assert result == 4

    def test_handle_return_all(self):
        lines = ["IF 1 = 1", "  RETURN ALL", "ENDIF"]
        tokens = ["RETURN", "ALL"]
        with pytest.raises(StopScript):
            result = self.engine.handle_return(tokens, lines, 2)

    def test_flatten(self):
        result = self.engine.flatten([[1, 2], [3, 4], [5]])
        assert result == [1, 2, 3, 4, 5]

    def test_evaluate_expression_simple(self):
        result = self.engine.evaluate_expression(["42"])
        assert result == 42

    def test_evaluate_expression_math(self):
        result = self.engine.evaluate_expression(["SIN", "(", "0", ")"])
        assert result == 0.0

    def test_evaluate_expressions_multiple(self):
        expressions = [["42"], ["3.14"]]
        results = self.engine.evaluate_expressions(expressions)
        assert results == [42, 3.14]

    def test_evaluate_tokens(self):
        tokens = ["42", "3.14"]
        results = self.engine.evaluate_tokens(tokens)
        assert results == [42, 3.14]

    @mock.patch('cstol_script_engine.clear_screen')
    def test_handle_clear_screen(self, mock_clear_screen):
        tokens = ["CLEAR", "\"INST ADCS\""]
        self.engine.handle_clear(tokens, 1)
        mock_clear_screen.assert_called_once_with("INST", "ADCS")

    @mock.patch('cstol_script_engine.clear_all_screens')
    def test_handle_clear_all(self, mock_clear_all):
        tokens = ["CLEAR", "ALL"]
        self.engine.handle_clear(tokens, 1)
        mock_clear_all.assert_called_once()

    @mock.patch('cstol_script_engine.display_screen')
    def test_handle_display(self, mock_display_screen):
        tokens = ["DISPLAY", "\"INST ADCS\""]
        self.engine.handle_display(tokens, 1)
        mock_display_screen.assert_called_once_with("INST", "ADCS")

    def test_handle_let_local_variable(self):
        tokens = ["LET", "$VAR", "=", "42"]
        self.engine.handle_let(tokens, 1)
        assert self.engine.variables.local_variables["$VAR"] == 42

    def test_handle_let_special_variable(self):
        tokens = ["LET", "$$TEST", "=", "42"]
        self.engine.handle_let(tokens, 1)
        assert self.engine.variables.special_variables["$$TEST"] == 42

    def test_handle_let_invalid_format(self):
        tokens = ["LET", "$VAR"]
        with pytest.raises(ValueError, match="Invalid LET command format"):
            self.engine.handle_let(tokens, 1)

    def test_handle_let_invalid_variable_name(self):
        tokens = ["LET", "VAR", "=", "42"]
        with pytest.raises(ValueError, match="Non-global variable name must start with"):
            self.engine.handle_let(tokens, 1)

    def test_handle_let_bad_expression(self):
        tokens = ["LET", "$VAR", "=", "1", "/", "0"]
        with pytest.raises(ValueError, match="Error evaluating expression"):
            self.engine.handle_let(tokens, 1)

    @mock.patch('cstol_script_engine.os.system')
    def test_handle_run_simple(self, mock_system):
        tokens = ["RUN", "echo hello"]
        self.engine.handle_run(tokens, 1)
        mock_system.assert_called_once_with("echo hello")

    def test_handle_run_invalid_format(self):
        tokens = ["RUN"]
        with pytest.raises(ValueError, match="Invalid RUN command format"):
            self.engine.handle_run(tokens, 1)

    @mock.patch('cstol_script_engine.wait')
    def test_handle_wait_indefinite(self, mock_wait):
        tokens = ["WAIT"]
        self.engine.handle_wait(tokens, 1)
        mock_wait.assert_called_once()

    @mock.patch('cstol_script_engine.wait')
    def test_handle_wait_with_reconstructed_timestamp(self, mock_wait):
        # Use cstol_tokenizer to get reconstructed timestamp tokens
        tokens = self.engine.cstol_tokenizer("WAIT 2025/123-12:30:45")
        self.engine.handle_wait(tokens, 1)
        # Should call wait with calculated seconds from now
        mock_wait.assert_called_once()

    def test_handle_wait_invalid_timestamp(self):
        tokens = ["WAIT", "invalid_time"]
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            self.engine.handle_wait(tokens, 1)

    @mock.patch('cstol_script_engine.connect_interface')
    def test_handle_switch_on(self, mock_connect):
        tokens = ["SWITCH", "ON", "INTERFACE1"]
        self.engine.handle_switch(tokens, 1)
        mock_connect.assert_called_once_with("INTERFACE1")

    @mock.patch('cstol_script_engine.disconnect_interface')
    def test_handle_switch_off(self, mock_disconnect):
        tokens = ["SWITCH", "OFF", "INTERFACE1"]
        self.engine.handle_switch(tokens, 1)
        mock_disconnect.assert_called_once_with("INTERFACE1")

    def test_handle_switch_invalid_action(self):
        tokens = ["SWITCH", "INVALID", "INTERFACE1"]
        with pytest.raises(ValueError, match="Invalid SWITCH action"):
            self.engine.handle_switch(tokens, 1)

    def test_handle_write_simple(self):
        tokens = ["WRITE", '"Hello World"']
        with mock.patch('builtins.print') as mock_print:
            self.engine.handle_write(tokens, 1)
            mock_print.assert_called_once_with("Hello World")

    def test_handle_write_with_format_hex(self):
        tokens = ["WRITE", "%X", "255"]
        with mock.patch('builtins.print') as mock_print:
            self.engine.handle_write(tokens, 1)
            mock_print.assert_called_once_with("FF")

    def test_handle_write_with_format_float(self):
        tokens = ["WRITE", "%F", "3.14159"]
        with mock.patch('builtins.print') as mock_print:
            self.engine.handle_write(tokens, 1)
            mock_print.assert_called_once_with("3.141590")

    def test_handle_write_invalid_format(self):
        tokens = ["WRITE", "%Z", "42"]
        with pytest.raises(ValueError, match="Invalid format"):
            self.engine.handle_write(tokens, 1)

    def test_handle_write_missing_value(self):
        tokens = ["WRITE", "%X"]
        with pytest.raises(ValueError, match="Missing value for format"):
            self.engine.handle_write(tokens, 1)

    def test_handle_check_simple_print(self):
        tokens = ["CHECK", "42"]
        with mock.patch('builtins.print') as mock_print:
            self.engine.handle_check(tokens, 1)
            mock_print.assert_called_once_with("CHECK SUCCESS: 42 = 42")

    def test_handle_check_vs_equal_success(self):
        tokens = ["CHECK", "42", "VS", "42"]
        with mock.patch('builtins.print') as mock_print:
            self.engine.handle_check(tokens, 1)
            mock_print.assert_called_once_with("CHECK SUCCESS: 42 = 42")

    def test_handle_check_vs_equal_failure(self):
        from openc3.script.exceptions import CheckError
        tokens = ["CHECK", "42", "VS", "43"]
        with pytest.raises(CheckError):
            self.engine.handle_check(tokens, 1)

    def test_handle_check_vs_range_success(self):
        tokens = ["CHECK", "42", "VS", "40", ":", "45"]
        with mock.patch('builtins.print') as mock_print:
            self.engine.handle_check(tokens, 1)
            mock_print.assert_called_once_with("CHECK SUCCESS: 42 = 42")

    def test_handle_check_vs_range_failure(self):
        from openc3.script.exceptions import CheckError
        tokens = ["CHECK", "42", "VS", "50", ":", "60"]
        with pytest.raises(CheckError):
            self.engine.handle_check(tokens, 1)

    def test_handle_check_invalid_range(self):
        tokens = ["CHECK", "42", "VS", "60", ":", "50"]
        with pytest.raises(ValueError, match="Invalid VS range"):
            self.engine.handle_check(tokens, 1)

    def test_handle_check_with_format(self):
        tokens = ["CHECK", "%X", "255"]
        with mock.patch('builtins.print') as mock_print:
            self.engine.handle_check(tokens, 1)
            mock_print.assert_called_once_with("CHECK SUCCESS: 255 = FF")

    def test_handle_if_true_condition(self):
        tokens = ["IF", "1", "=", "1"]
        lines = ["IF 1 = 1", "  WRITE \"TRUE\"", "ENDIF"]
        result = self.engine.handle_if(tokens, lines, 1)
        assert result == 2

    def test_handle_if_false_condition(self):
        tokens = ["IF", "1", "=", "2"]
        lines = ["IF 1 = 2", "  WRITE \"TRUE\"", "ENDIF"]
        result = self.engine.handle_if(tokens, lines, 1)
        assert result == 3

    def test_handle_if_no_endif(self):
        tokens = ["IF", "1", "=", "2"]
        lines = ["", ""]
        with pytest.raises(ValueError, match="No matching ENDIF"):
            self.engine.handle_if(tokens, lines, 0)

    def test_handle_end_endif(self):
        tokens = ["ENDIF"]
        result = self.engine.handle_end(tokens, 5)
        assert result == 6

    def test_handle_end_endloop_infinite(self):
        self.engine.variables.loop_stack.append([10, None, 1])
        tokens = ["ENDLOOP"]
        result = self.engine.handle_end(tokens, 15)
        assert result == 10

    def test_handle_end_endloop_counted(self):
        self.engine.variables.loop_stack.append([10, 3, 1])
        tokens = ["ENDLOOP"]
        result = self.engine.handle_end(tokens, 15)
        assert result == 10
        assert self.engine.variables.loop_stack[0][1] == 2

    def test_handle_end_endloop_count_finished(self):
        self.engine.variables.loop_stack.append([10, 1, 1])
        tokens = ["ENDLOOP"]
        result = self.engine.handle_end(tokens, 15)
        assert result == 16
        assert len(self.engine.variables.loop_stack) == 0

    def test_handle_end_unexpected(self):
        tokens = ["END"]
        with pytest.raises(ValueError, match="Unexpected END command"):
            self.engine.handle_end(tokens, 1)

    def test_handle_goto(self):
        tokens = ["GOTO", "LABEL1"]
        lines = ["", "LABEL1:", ""]
        result = self.engine.handle_go(tokens, lines, 0)
        assert result == 2

    def test_handle_go_to(self):
        tokens = ["GO", "TO", "LABEL1"]
        lines = ["", "LABEL1:", ""]
        result = self.engine.handle_go(tokens, lines, 0)
        assert result == 2

    def test_handle_goto_label_not_found(self):
        tokens = ["GOTO", "MISSING"]
        lines = ["", "LABEL1:", ""]
        with pytest.raises(ValueError, match="Label 'MISSING:' not found"):
            self.engine.handle_go(tokens, lines, 0)

    def test_handle_goto_invalid_format(self):
        tokens = ["GOTO"]
        with pytest.raises(ValueError, match="Invalid GOTO command format"):
            self.engine.handle_go(tokens, lines=[], line_no=1)

    def test_handle_escape(self):
        lines = ["", "LOOP", "", "ESCAPE", "", "ENDLOOP", ""]
        result = self.engine.handle_escape(["ESCAPE"], lines, 4)
        assert result == 6

    def test_handle_escape_no_endloop(self):
        lines = ["", "ESCAPE", ""]
        with pytest.raises(ValueError, match="No matching ENDLOOP found"):
            self.engine.handle_escape(["ESCAPE"], lines, 1)

    @mock.patch('cstol_script_engine.start')
    def test_handle_start_simple(self, mock_start):
        tokens = ["START", "PROC1"]
        self.engine.handle_start(tokens, 1)
        mock_start.assert_called_once_with("PROC1", bind_variables=False)

    @mock.patch('cstol_script_engine.start')
    @mock.patch('cstol_script_engine.os.environ', {})
    def test_handle_start_with_args(self, mock_start):
        tokens = ["START", "PROC1", "1", ",", "2"]
        with mock.patch.dict('os.environ', {}, clear=True):
            self.engine.handle_start(tokens, 1)
            mock_start.assert_called_once_with("PROC1", bind_variables=False)

    def test_handle_proc_simple(self):
        tokens = ["PROC", "TEST_PROC"]
        self.engine.handle_proc(tokens, 1)
        # Should not raise any errors

    def test_handle_proc_with_variables(self):
        tokens = ["PROC", "TEST_PROC", "$VAR1", ",", "$VAR2"]
        with mock.patch('cstol_script_engine.os.getenv') as mock_getenv:
            mock_getenv.side_effect = lambda x: f"value_{x}"
            self.engine.handle_proc(tokens, 1)
            assert self.engine.variables.local_variables["$VAR1"] == "value_CSTOL_ARG_0"

    def test_handle_proc_invalid_variable(self):
        tokens = ["PROC", "TEST_PROC", "VAR1"]
        with pytest.raises(ValueError, match="Invalid variable"):
            self.engine.handle_proc(tokens, 1)

    @mock.patch('cstol_script_engine.cmd')
    def test_handle_cmd_simple(self, mock_cmd):
        tokens = ["ACTIVATE", "TARGET1"]
        self.engine.handle_cmd(tokens, 1)
        mock_cmd.assert_called_once_with("TARGET1", "ACTIVATE", {})

    @mock.patch('cstol_script_engine.cmd')
    def test_handle_cmd_with_to(self, mock_cmd):
        tokens = ["SET", "TARGET1", "PARAM1", "TO", "42"]
        self.engine.handle_cmd(tokens, 1)
        mock_cmd.assert_called_once_with("TARGET1", "SET", {"PARAM1": 42})

    @mock.patch('cstol_script_engine.cmd')
    def test_handle_cmd_now(self, mock_cmd):
        tokens = ["NOW", "ACTIVATE", "TARGET1"]
        self.engine.handle_cmd(tokens, 1)
        mock_cmd.assert_called_once_with("TARGET1", "ACTIVATE", {})

    @mock.patch('cstol_script_engine.cmd')
    def test_handle_cmd_turn_on(self, mock_cmd):
        tokens = ["TURN", "ON", "TARGET1"]
        self.engine.handle_cmd(tokens, 1)
        mock_cmd.assert_called_once_with("TARGET1", "TURNON", {})

    def test_handle_cmd_turn_invalid(self):
        tokens = ["TURN", "INVALID", "TARGET1"]
        with pytest.raises(ValueError, match="TURN and FORCE must be followed by ON or OFF"):
            self.engine.handle_cmd(tokens, 1)

    def test_get_special_variable_current_time(self):
        import datetime
        result = self.engine.variables.get_special_variable("$$CURRENT_TIME")
        assert isinstance(result, float)

    def test_get_special_variable_sc_time(self):
        result = self.engine.variables.get_special_variable("$$SC_TIME")
        assert isinstance(result, float)

    def test_set_special_variable_clp_stp_interval(self):
        self.engine.variables.set_special_variable("$$CLP_STP_INTERVAL", 10)
        assert self.engine.variables.special_variables["$$CLP_STP_INTERVAL"] == 10
        assert self.engine.variables.special_variables["$$STEP_INTERVAL"] == 10

    def test_set_special_variable_step_interval(self):
        self.engine.variables.set_special_variable("$$STEP_INTERVAL", 2)
        assert self.engine.variables.special_variables["$$CLP_STP_INTERVAL"] == 2
        assert self.engine.variables.special_variables["$$STEP_INTERVAL"] == 2

    def test_set_special_variable_clp_step_mode(self):
        with mock.patch('cstol_script_engine.run_mode') as mock_cmd:
            self.engine.variables.set_special_variable("$$CLP_STEP_MODE", "GO")
            mock_cmd.assert_called_once()
        with mock.patch('cstol_script_engine.run_mode') as mock_cmd:
            self.engine.variables.set_special_variable("$$CLP_STEP_MODE", "PAUSE")
            mock_cmd.assert_called_once()
        with mock.patch('cstol_script_engine.step_mode') as mock_cmd:
            self.engine.variables.set_special_variable("$$CLP_STEP_MODE", "WAIT")
            mock_cmd.assert_called_once()
        with pytest.raises(ValueError, match="Invalid step mode"):
            self.engine.variables.set_special_variable("$$CLP_STEP_MODE", "OTHER")

    def test_set_special_variable_step_mode(self):
        with mock.patch('cstol_script_engine.run_mode') as mock_cmd:
            self.engine.variables.set_special_variable("$$STEP_MODE", "GO")
            mock_cmd.assert_called_once()
        with mock.patch('cstol_script_engine.run_mode') as mock_cmd:
            self.engine.variables.set_special_variable("$$STEP_MODE", "PAUSE")
            mock_cmd.assert_called_once()
        with mock.patch('cstol_script_engine.step_mode') as mock_cmd:
            self.engine.variables.set_special_variable("$$STEP_MODE", "WAIT")
            mock_cmd.assert_called_once()
        with pytest.raises(ValueError, match="Invalid step mode"):
            self.engine.variables.set_special_variable("$$STEP_MODE", "OTHER")

    def test_run_line_with_continuation(self):
        self.engine.saved_tokens = ["WRITE"]
        result = self.engine.run_line("'Hello'", [], "test.txt", 1)
        assert result == 2  # Should go to next line
        assert self.engine.saved_tokens is None

    def test_run_line_with_continuation_ampersand(self):
        result = self.engine.run_line("WRITE 'Hello' &", [], "test.txt", 1)
        assert result == 2  # Should go to next line
        assert self.engine.saved_tokens == ["WRITE", "'Hello'"]

    def test_run_line_with_comment(self):
        with mock.patch('builtins.print') as mock_print:
            result = self.engine.run_line("WRITE 'Hello' ; This is a comment", [], "test.txt", 1)
            assert result == 2
            mock_print.assert_called_once_with("Hello")

    def test_run_line_with_label(self):
        result = self.engine.run_line("LABEL1:", [], "test.txt", 1)
        assert result == 2

    def test_run_line_begin(self):
        result = self.engine.run_line("BEGIN", [], "test.txt", 1)
        assert result == 2

    def test_run_line_unsupported_keyword(self):
        with mock.patch('builtins.print') as mock_print:
            result = self.engine.run_line("CANCEL", [], "test.txt", 1)
            assert result == 2
            mock_print.assert_called_once_with("Ignoring Unsupported Keyword: CANCEL")

    def test_run_line_unknown_keyword(self):
        with pytest.raises(ValueError, match="Unknown keyword 'UNKNOWN'"):
            self.engine.run_line("UNKNOWN", [], "test.txt", 1)

    def test_extract_expressions_empty_expression(self):
        result = self.engine.extract_expressions(["A", ",", ",", "B"], ",")
        assert result == [["A"], [], ["B"]]

    def test_extract_expressions_no_separator(self):
        result = self.engine.extract_expressions(["A", "B", "C"], ",")
        assert result == [["A", "B", "C"]]

    def test_handle_else_simple(self):
        tokens = ["ELSE"]
        with pytest.raises(ValueError, match="No matching ENDIF for ELSE"):
            result = self.engine.handle_else(tokens, [], 5)

    def test_handle_else_with_endif(self):
        tokens = ["ELSE"]
        lines = ["IF TRUE", "WRITE 'TRUE'", "ELSE", "WRITE 'HELLO'", "ENDIF"]
        result = self.engine.handle_else(tokens, lines, 3)
        assert result == 5

    def test_handle_else_elseif(self):
        tokens = ["ELSEIF", "1", "=", "1"]
        lines = ["ELSEIF 1 = 1", "  WRITE \"TRUE\"", "ENDIF"]
        result = self.engine.handle_else(tokens, lines, 1)
        assert result == 2

    def test_handle_else_elseif_false(self):
        tokens = ["ELSEIF", "1", "=", "2"]
        lines = ["ELSEIF 1 = 1", "  WRITE \"TRUE\"", "ENDIF"]
        result = self.engine.handle_else(tokens, lines, 1)
        assert result == 3

    def test_handle_else_else_if(self):
        tokens = ["ELSE", "IF", "1", "=", "1"]
        lines = ["ELSE IF 1 = 1", "  WRITE \"TRUE\"", "ENDIF"]
        result = self.engine.handle_else(tokens, lines, 1)
        assert result == 2

    def test_handle_let_global_variable_invalid(self):
        tokens = ["LET", "GLOBAL_VAR", "=", "42"]
        with pytest.raises(ValueError, match="Non-global variable name must start with"):
            self.engine.handle_let(tokens, 1)

    @mock.patch('cstol_script_engine.set_tlm')
    def test_handle_let_global_variable_with_item(self, mock_set_tlm):
        # This tests the global variable path with item_name
        tokens = ["LET", "TARGET", "ITEM", "=", "42"]
        self.engine.handle_let(tokens, 1)
        mock_set_tlm.assert_called_once_with("TARGET LATEST ITEM = 42")

    def test_handle_declare_invalid_equals(self):
        tokens = ["DECLARE", "VARIABLE", "$TEST", "!=", "42"]
        with pytest.raises(ValueError, match="Expected '=' after variable name"):
            self.engine.handle_declare(tokens, 1)

    def test_handle_loop_invalid_format(self):
        tokens = ["LOOP", "5", "extra"]
        with pytest.raises(ValueError, match="Invalid LOOP command format"):
            self.engine.handle_loop(tokens, 1)

    def test_handle_proc_invalid_variable_with_comma(self):
        tokens = ["PROC", "TEST_PROC", "$VAR1,", "VAR2"]
        with pytest.raises(ValueError, match="Invalid variable"):
            self.engine.handle_proc(tokens, 1)

    @mock.patch('cstol_script_engine.os.system')
    def test_handle_run_with_arguments(self, mock_system):
        tokens = ["RUN", "script.sh", "arg1", ",", "arg2"]
        self.engine.handle_run(tokens, 1)
        mock_system.assert_called_once_with('script.sh "arg1" "arg2"')

    @mock.patch('cstol_script_engine.send_raw')
    def test_handle_send_invalid_format(self, mock_send):
        tokens = ["SEND", "data", "TO"]  # Missing target
        with pytest.raises(ValueError, match="Invalid SEND command format"):
            self.engine.handle_send(tokens, 1)

    @mock.patch('cstol_script_engine.get_target_file')
    @mock.patch('cstol_script_engine.send_raw')
    def test_handle_load(self, mock_send, mock_get_file):
        mock_file = mock.MagicMock()
        mock_file.read.return_value = b"test_data"
        mock_get_file.return_value = mock_file

        tokens = ["LOAD", "interface1", "AT", "location1", "FROM", "\"file.txt\""]
        self.engine.handle_load(tokens, 1)
        mock_send.assert_called_once_with("interface1", b"test_data")

    def test_handle_load_invalid_at_format(self):
        tokens = ["LOAD", "interface1", "AT"]  # Missing location and FROM
        with pytest.raises(ValueError, match="Invalid LOAD command format"):
            self.engine.handle_load(tokens, 1)

    def test_handle_load_invalid_from_format(self):
        tokens = ["LOAD", "interface1", "AT", "location1", "FROM"]  # Missing filename
        with pytest.raises(ValueError, match="Invalid LOAD command format"):
            self.engine.handle_load(tokens, 1)

    @mock.patch('cstol_script_engine.wait_expression')
    def test_handle_wait_with_expression_and_not_timeout(self, mock_wait_expr):
        mock_wait_expr.return_value = True
        self.engine.variables.local_variables["$VAR"] = 2
        tokens = ["WAIT", "$VAR", "=", "1", "OR", "FOR", "12:30:45"]
        self.engine.handle_wait(tokens, 1)
        mock_wait_expr.assert_called_once_with(mock.ANY, 45045, 1.0, globals=mock.ANY)
        assert self.engine.variables.get_special_variable("$$ERROR") == "NO_ERROR"

    @mock.patch('cstol_script_engine.wait_expression')
    def test_handle_wait_with_expression_and_timeout(self, mock_wait_expr):
        mock_wait_expr.return_value = False
        self.engine.variables.local_variables["$VAR"] = 2
        tokens = ["WAIT", "$VAR", "=", "1", "OR", "FOR", "12:30:45"]
        self.engine.handle_wait(tokens, 1)
        mock_wait_expr.assert_called_once_with(mock.ANY, 45045, 1.0, globals=mock.ANY)
        assert self.engine.variables.get_special_variable("$$ERROR") == "TIME_OUT"

    @mock.patch('cstol_script_engine.wait_expression')
    def test_handle_wait_with_expression_and_abs_timeout_future(self, mock_wait_expr):
        self.engine.variables.local_variables["$VAR"] = 2
        tokens = ["WAIT", "$VAR", "=", "1", "OR", "FOR", "2038/1-12:30:45"]
        self.engine.handle_wait(tokens, 1)
        mock_wait_expr.assert_called_once()

    @mock.patch('cstol_script_engine.wait_expression')
    def test_handle_wait_with_expression_and_abs_timeout_past(self, mock_wait_expr):
        self.engine.variables.local_variables["$VAR"] = 2
        tokens = ["WAIT", "$VAR", "=", "1", "OR", "FOR", "1980/1-12:30:45"]
        self.engine.handle_wait(tokens, 1)
        mock_wait_expr.assert_called_once()

    @mock.patch('cstol_script_engine.wait_expression')
    def test_handle_wait_with_expression_no_timeout(self, mock_wait_expr):
        mock_wait_expr.return_value = True
        self.engine.variables.local_variables["$VAR"] = 2
        tokens = ["WAIT", "$VAR", "=", "1"]
        self.engine.handle_wait(tokens, 1)
        mock_wait_expr.assert_called_once_with(mock.ANY, 1000000000, 1.0, globals=mock.ANY)
        assert self.engine.variables.get_special_variable("$$ERROR") == "NO_ERROR"

    @mock.patch('cstol_script_engine.wait_expression')
    def test_handle_wait_with_expression_infinite_timeout(self, mock_wait_expr):
        mock_wait_expr.return_value = False
        self.engine.variables.local_variables["$VAR"] = 2
        tokens = ["WAIT", "$VAR", "=", "1"]
        self.engine.handle_wait(tokens, 1)
        mock_wait_expr.assert_called_once_with(mock.ANY, 1000000000, 1.0, globals=mock.ANY)
        assert self.engine.variables.get_special_variable("$$ERROR") == "TIME_OUT"

    def test_handle_wait_invalid_timeout_timestamp(self):
        self.engine.variables.local_variables["$VAR"] = 2
        tokens = ["WAIT", "$VAR", "=", "1", "OR", "FOR", "invalid"]
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            self.engine.handle_wait(tokens, 1)

    def test_handle_cmd_malformed_to(self):
        tokens = ["SET", "TARGET1", "TO", "42", "extra"]
        with pytest.raises(ValueError, match="Error evaluating expression"):
            self.engine.handle_cmd(tokens, 1)

    def test_build_python_expression(self):
        self.engine.variables.local_variables["$VAR"] = 1
        tokens = ["$VAR", "=", "42"]
        result = self.engine.build_python_expression(tokens)
        assert result == "1 == 42"

    def test_build_python_expression_local_variable_string_conversion(self):
        # Test local variable string conversion in build_python_expression (line 212)
        self.engine.variables.local_variables['$TEST'] = 'string_value'
        result = self.engine.build_python_expression(['$TEST'])
        assert '"string_value"' in result

    def test_build_python_expression_dn(self):
        tokens = ["42DN", "+", "12", "DN"]
        result = self.engine.build_python_expression(tokens)
        assert result == "42 + 12"

    def test_build_python_expression_eu(self):
        tokens = ["10A", "-", "2", "MA"]
        result = self.engine.build_python_expression(tokens)
        assert result == "10 - 2"

    def test_build_python_expression_already_quoted_single(self):
        # Test single quotes are preserved as-is
        tokens = ["'hello world'"]
        result = self.engine.build_python_expression(tokens)
        assert result == "'hello world'"

    def test_build_python_expression_special_variable_string(self):
        # Test special variable that returns a string
        self.engine.variables.special_variables["$$TEST"] = "test_value"
        tokens = ["$$TEST"]
        result = self.engine.build_python_expression(tokens)
        assert '"test_value"' in result

    def test_build_python_expression_local_variable_string(self):
        # Test local variable that returns a string
        self.engine.variables.local_variables["$TEST"] = "test_value"
        tokens = ["$TEST"]
        result = self.engine.build_python_expression(tokens)
        assert '"test_value"' in result

    def test_build_python_expression_special_variable_non_string(self):
        # Test line 212: special variable non-string value
        self.engine.variables.set_special_variable('$$TEST', 42)
        result = self.engine.build_python_expression(['$$TEST'])
        assert '42' in result

    def test_run_line_empty_tokens(self):
        # Test with a line that results in no tokens (just whitespace/comments)
        result = self.engine.run_line("  ; just a comment", [], "test.txt", 1)
        assert result == 2

    def test_run_line_with_tokens_ending_ampersand(self):
        # Test continuation line handling when tokens list is not empty
        result = self.engine.run_line("WRITE 'test' &", [], "test.txt", 1)
        assert result == 2
        assert self.engine.saved_tokens is not None

    def test_handle_cmd_force_on(self):
        tokens = ["FORCE", "ON", "TARGET1"]
        with mock.patch('cstol_script_engine.cmd') as mock_cmd:
            self.engine.handle_cmd(tokens, 1)
            mock_cmd.assert_called_once_with("TARGET1", "FORCEON", {})

    def test_handle_cmd_force_off(self):
        tokens = ["FORCE", "OFF", "TARGET1"]
        with mock.patch('cstol_script_engine.cmd') as mock_cmd:
            self.engine.handle_cmd(tokens, 1)
            mock_cmd.assert_called_once_with("TARGET1", "FORCEOFF", {})

    def test_handle_cmd_by_clause(self):
        tokens = ["SET", "TARGET1", "PARAM1", "BY", "42"]
        with mock.patch('cstol_script_engine.cmd') as mock_cmd:
            with mock.patch.object(self.engine, 'evaluate_expression', return_value=42):
                with mock.patch.object(self.engine, 'evaluate_tokens', return_value=["TARGET1"]):
                    with mock.patch.object(self.engine, 'extract_expressions',
                                           side_effect=[
                                               [["TARGET1"], ["PARAM1", "BY", "42"]],  # TO expressions
                                               [["TARGET1", "PARAM1"], ["42"]],        # BY expressions
                                               [],  # FROM expressions
                                               []   # WITH expressions
                                           ]):
                        self.engine.handle_cmd(tokens, 1)
                        mock_cmd.assert_called_once()

    def test_handle_cmd_from_clause(self):
        tokens = ["SET", "TARGET1", "PARAM1", "FROM", "42"]
        with mock.patch('cstol_script_engine.cmd') as mock_cmd:
            self.engine.handle_cmd(tokens, 1)
            mock_cmd.assert_called_once_with("TARGET1", "SET", {"PARAM1": 42})

    def test_handle_cmd_cmd_with_to_clause(self):
        tokens = ["CMD", "TARGET1", "COMMAND1", "TO", "42"]
        with mock.patch('cstol_script_engine.cmd') as mock_cmd:
            self.engine.handle_cmd(tokens, 1)
            mock_cmd.assert_called_once_with("TARGET1", "COMMAND1", {"VALUE": 42})

    def test_handle_cmd_malformed_to_error(self):
        # Test malformed TO command (line 573) - too many parts before TO
        with pytest.raises(ValueError, match="Malformed TO cmd"):
            self.engine.handle_cmd(['CMD', 'TARGET', 'COMMAND', 'PARAM', 'TO', 'VALUE'], 1)

    def test_handle_cmd_with_with_clause(self):
        # Test WITH clause handling (lines 576-586)
        with mock.patch('cstol_script_engine.cmd') as mock_cmd:
            tokens = ['CMD', 'SPACECRAFT', 'TEST_CMD', 'WITH', 'PARAM1', '42', ',', 'PARAM2', 'abc']
            self.engine.handle_cmd(tokens, 1)
            mock_cmd.assert_called_with("SPACECRAFT", "TEST_CMD", {"PARAM1": 42, "PARAM2": "abc"})

    def test_handle_cmd_no_clauses(self):
        # Test command with no clauses (line 592)
        with mock.patch('cstol_script_engine.cmd') as mock_cmd:
            tokens = ['CMD', 'TEST_CMD', 'SPACECRAFT']
            self.engine.handle_cmd(tokens, 1)
            mock_cmd.assert_called_once_with("TEST_CMD", "SPACECRAFT", {})

    def test_cmd_with_just_target_name(self):
        with mock.patch('cstol_script_engine.cmd') as mock_cmd:
            tokens = ['SET', 'SPACECRAFT', 'TO', '42']
            self.engine.handle_cmd(tokens, 1)
            mock_cmd.assert_called_once_with("SPACECRAFT", "SET", {"VALUE": 42})

    def test_handle_check_format_missing_value(self):
        tokens = ["CHECK", "%X"]
        with pytest.raises(ValueError, match="Missing value for format"):
            self.engine.handle_check(tokens, 1)

    def test_handle_check_unknown_format(self):
        tokens = ["CHECK", "%Z"]
        with pytest.raises(ValueError, match="Invalid format"):
            self.engine.handle_check(tokens, 1)

    def test_handle_check_invalid_vs_format_too_many_colons(self):
        tokens = ["CHECK", "42", "VS", "40", ":", "45", ":", "50"]
        with pytest.raises(ValueError, match="Invalid VS format"):
            self.engine.handle_check(tokens, 1)

    def test_handle_write_format_octal(self):
        tokens = ["WRITE", "%O", "8"]
        with mock.patch('builtins.print') as mock_print:
            with mock.patch.object(self.engine, 'evaluate_expression', return_value=8):
                self.engine.handle_write(tokens, 1)
                mock_print.assert_called_once_with("10")

    def test_handle_write_format_binary(self):
        tokens = ["WRITE", "%B", "5"]
        with mock.patch('builtins.print') as mock_print:
            with mock.patch.object(self.engine, 'evaluate_expression', return_value=5):
                self.engine.handle_write(tokens, 1)
                mock_print.assert_called_once_with("101")

    def test_handle_write_format_integer(self):
        tokens = ["WRITE", "%I", "42"]
        with mock.patch('builtins.print') as mock_print:
            with mock.patch.object(self.engine, 'evaluate_expression', return_value=42):
                self.engine.handle_write(tokens, 1)
                mock_print.assert_called_once_with("42")

    def test_handle_write_format_decimal(self):
        tokens = ["WRITE", "%D", "42"]
        with mock.patch('builtins.print') as mock_print:
            with mock.patch.object(self.engine, 'evaluate_expression', return_value=42):
                self.engine.handle_write(tokens, 1)
                mock_print.assert_called_once_with("42")

    def test_handle_write_format_scientific(self):
        tokens = ["WRITE", "%E", "1234.5"]
        with mock.patch('builtins.print') as mock_print:
            with mock.patch.object(self.engine, 'evaluate_expression', return_value=1234.5):
                self.engine.handle_write(tokens, 1)
                mock_print.assert_called_once_with("1.234500e+03")

    def test_handle_check_format_all_types(self):
        # Test all the format types for CHECK command
        format_tests = [
            ("%O", 8, "10"),
            ("%B", 5, "101"),
            ("%I", 42, "42"),
            ("%D", 42, "42"),
            ("%E", 1234.5, "1.234500e+03")
        ]

        for fmt, value, expected in format_tests:
            tokens = ["CHECK", fmt, str(value)]
            with mock.patch('builtins.print') as mock_print:
                self.engine.handle_check(tokens, 1)
                mock_print.assert_called_once_with(f"CHECK SUCCESS: {value} = {expected}")

    @mock.patch('cstol_script_engine.os.environ', {})
    def test_handle_start_with_environment_variables(self, ):
        tokens = ["START", "\"PROC1\"", "arg1", ",", "arg2"]
        with mock.patch('cstol_script_engine.start') as mock_start:
            with mock.patch.dict('os.environ', {}, clear=True):
                self.engine.handle_start(tokens, 1)
                mock_start.assert_called_once_with("PROC1", bind_variables=False)

    def test_run_text_without_bind_variables(self):
        # Test the run_text method that creates new variable scope
        original_vars = self.engine.variables
        with mock.patch.object(self.engine.__class__.__bases__[0], 'run_text') as mock_super_run:
            self.engine.run_text("WRITE 'test'", bind_variables=False)
            mock_super_run.assert_called_once()
            # Should restore original variables
            assert self.engine.variables == original_vars

    def test_run_text_with_bind_variables(self):
        # Test the run_text method that preserves variable scope
        original_vars = self.engine.variables
        with mock.patch.object(self.engine.__class__.__bases__[0], 'run_text') as mock_super_run:
            self.engine.run_text("WRITE 'test'", bind_variables=True)
            mock_super_run.assert_called_once()
            # Should keep same variables
            assert self.engine.variables == original_vars

    def test_run_line_final_label_check(self):
        # Test the final label check in run_line
        # This covers the "next" statement in the final else clause
        result = self.engine.run_line("LABEL1:", [], "test.txt", 1)
        assert result == 2

    def test_run_line_label_with_keyword(self):
        result = self.engine.run_line("LABEL1: RETURN", ["LABEL1: RETURN", "WRITE 'test'"], "test.txt", 1)
        assert result == 3

    def test_build_python_expression_operator_conversions(self):
        self.engine.variables.local_variables["$VAR"] = 1
        self.engine.variables.local_variables["$VAR2"] = 2

        # Test /= operator conversion (line 235-237)
        result = self.engine.build_python_expression(['$VAR', '/=', '5'])
        assert result == "1 != 5"

        # Test = operator conversion (line 239-241)
        result = self.engine.build_python_expression(['$VAR', '=', '5'])
        assert result == "1 == 5"

        # Test AND operator conversion (line 245-247)
        result = self.engine.build_python_expression(['$VAR', 'AND', '$VAR2'])
        assert result == "1 and 2"

        # Test OR operator conversion (line 249-251)
        result = self.engine.build_python_expression(['$VAR', 'OR', '$VAR2'])
        assert result == "1 or 2"

        # Test NOT operator conversion (line 253-255)
        result = self.engine.build_python_expression(['NOT', '$VAR'])
        assert result == "not 1"

    def test_handle_write_invalid_format_error(self):
        # Test invalid format error (line 446)
        with pytest.raises(ValueError, match="Invalid format"):
            self.engine.handle_write(['WRITE', '%Z', '42'], 1)

    def test_handle_write_missing_value_for_format(self):
        # Test missing value for format (line 448)
        with pytest.raises(ValueError, match="Missing value for format"):
            self.engine.handle_write(['WRITE', '%X'], 1)

    def test_handle_send_command(self):
        # Test SEND command (lines 809-812)
        with mock.patch('cstol_script_engine.send_raw') as mock_send:
            tokens = ['SEND', 'h#0102', 'TO', 'INTERFACE1']
            self.engine.handle_send(tokens, 1)
            mock_send.assert_called_once_with("INTERFACE1", b'\x01\x02')

    def test_handle_send_invalid_format(self):
        # Test SEND invalid format
        with pytest.raises(ValueError, match="Invalid SEND command format"):
            self.engine.handle_send(['SEND', 'data'], 1)

    def test_run_line_ask_keyword(self):
        # Test ASK keyword case (line 943)
        with mock.patch.object(self.engine, 'handle_ask') as mock_ask:
            self.engine.run_line("ASK 'Enter value'", [], "test.txt", 1)
            mock_ask.assert_called_once()

    def test_run_line_unsupported_keywords(self):
        # Test unsupported keywords (line 952)
        with mock.patch('builtins.print') as mock_print:
            self.engine.run_line("CANCEL", [], "test.txt", 1)
            mock_print.assert_called_with("Ignoring Unsupported Keyword: CANCEL")

        with mock.patch('builtins.print') as mock_print:
            self.engine.run_line("CHECKPOINT", [], "test.txt", 1)
            mock_print.assert_called_with("Ignoring Unsupported Keyword: CHECKPOINT")

    def test_run_line_cmd_variants(self):
        # Test various CMD variants (line 959)
        with mock.patch.object(self.engine, 'handle_cmd') as mock_cmd:
            self.engine.run_line("ACTIVATE", [], "test.txt", 1)
            mock_cmd.assert_called_once()

        with mock.patch.object(self.engine, 'handle_cmd') as mock_cmd:
            self.engine.run_line("ARM", [], "test.txt", 1)
            mock_cmd.assert_called_once()

        with mock.patch.object(self.engine, 'handle_cmd') as mock_cmd:
            self.engine.run_line("FORCE", [], "test.txt", 1)
            mock_cmd.assert_called_once()

    def test_run_line_declare_keyword(self):
        # Test DECLARE keyword (line 961)
        with mock.patch.object(self.engine, 'handle_declare') as mock_declare:
            self.engine.run_line("DECLARE $VAR", [], "test.txt", 1)
            mock_declare.assert_called_once()

    def test_run_line_display_keyword(self):
        # Test DISPLAY keyword (line 963)
        with mock.patch.object(self.engine, 'handle_display') as mock_display:
            self.engine.run_line("DISPLAY 'test'", [], "test.txt", 1)
            mock_display.assert_called_once()

    def test_run_line_else_keyword(self):
        # Test ELSE keyword (line 965)
        with mock.patch.object(self.engine, 'handle_else') as mock_else:
            mock_else.return_value = 2
            result = self.engine.run_line("ELSE", [], "test.txt", 1)
            mock_else.assert_called_once()
            assert result == 2

    def test_run_line_end_keyword(self):
        # Test END keyword (line 967)
        with mock.patch.object(self.engine, 'handle_end') as mock_end:
            self.engine.run_line("END", [], "test.txt", 1)
            mock_end.assert_called_once()

    def test_run_line_escape_keyword(self):
        # Test ESCAPE keyword (line 969)
        with mock.patch.object(self.engine, 'handle_escape') as mock_escape:
            mock_escape.return_value = 2
            result = self.engine.run_line("ESCAPE", [], "test.txt", 1)
            mock_escape.assert_called_once()
            assert result == 2

    def test_run_line_goto_keyword(self):
        # Test GOTO keyword (line 971)
        with mock.patch.object(self.engine, 'handle_go') as mock_go:
            mock_go.return_value = 2
            result = self.engine.run_line("GOTO LABEL1", [], "test.txt", 1)
            mock_go.assert_called_once()
            assert result == 2

    def test_run_line_if_keyword(self):
        # Test IF keyword (line 973)
        with mock.patch.object(self.engine, 'handle_if') as mock_if:
            mock_if.return_value = 2
            result = self.engine.run_line("IF $VAR = 1", [], "test.txt", 1)
            mock_if.assert_called_once()
            assert result == 2

    def test_run_line_let_keyword(self):
        # Test LET keyword (line 975)
        with mock.patch.object(self.engine, 'handle_let') as mock_let:
            self.engine.run_line("LET $VAR = 42", [], "test.txt", 1)
            mock_let.assert_called_once()

    def test_run_line_load_keyword(self):
        # Test LOAD keyword (line 977)
        with mock.patch.object(self.engine, 'handle_load') as mock_load:
            self.engine.run_line("LOAD data AT 2024/001-12:00:00 FROM file.txt", [], "test.txt", 1)
            mock_load.assert_called_once()

    def test_run_line_loop_keyword(self):
        # Test LOOP keyword (line 979)
        with mock.patch.object(self.engine, 'handle_loop') as mock_loop:
            self.engine.run_line("LOOP", [], "test.txt", 1)
            mock_loop.assert_called_once()

    def test_run_line_proc_keyword(self):
        # Test PROC keyword (line 981)
        with mock.patch.object(self.engine, 'handle_proc') as mock_proc:
            self.engine.run_line("PROC test_proc", [], "test.txt", 1)
            mock_proc.assert_called_once()

    def test_run_line_run_keyword(self):
        # Test RUN keyword (line 983)
        with mock.patch.object(self.engine, 'handle_run') as mock_run:
            self.engine.run_line("RUN script.cstol", [], "test.txt", 1)
            mock_run.assert_called_once()

    def test_run_line_send_keyword(self):
        # Test SEND keyword (line 985)
        with mock.patch.object(self.engine, 'handle_send') as mock_send:
            self.engine.run_line("SEND data TO interface", [], "test.txt", 1)
            mock_send.assert_called_once()

    def test_run_line_start_keyword(self):
        # Test START keyword (line 987)
        with mock.patch.object(self.engine, 'handle_start') as mock_start:
            self.engine.run_line("START proc_name", [], "test.txt", 1)
            mock_start.assert_called_once()

    def test_run_line_switch_keyword(self):
        # Test SWITCH keyword (line 989)
        with mock.patch.object(self.engine, 'handle_switch') as mock_switch:
            self.engine.run_line("SWITCH ON", [], "test.txt", 1)
            mock_switch.assert_called_once()

    def test_run_line_wait_keyword(self):
        # Test WAIT keyword (line 991)
        with mock.patch.object(self.engine, 'handle_wait') as mock_wait:
            self.engine.run_line("WAIT", [], "test.txt", 1)
            mock_wait.assert_called_once()

    def test_run_line_write_keyword(self):
        # Test WRITE keyword (line 993)
        with mock.patch.object(self.engine, 'handle_write') as mock_write:
            self.engine.run_line("WRITE 'test'", [], "test.txt", 1)
            mock_write.assert_called_once()

    def test_run_line_unknown_keyword_error(self):
        # Test unknown keyword error (line 998)
        with pytest.raises(ValueError, match="Unknown keyword"):
            self.engine.run_line("UNKNOWN_KEYWORD", [], "test.txt", 1)

    def test_handle_check_invalid_vs_format_too_many_colons(self):
        # Test invalid VS format with too many colons
        # Use single token to avoid tlm conversion
        with pytest.raises(ValueError, match="Invalid range format"):
            self.engine.handle_check(['CHECK', 'VALUE', 'VS', '1:2:3:4'], 1)

    def test_split_vs_tokens_preserves_timestamps(self):
        # Test that valid timestamps are not split by colon handling
        timestamp_tokens = ['12:34:56', '2024/001-12:34:56.789']
        result = self.engine.split_vs_tokens_on_colon(timestamp_tokens)
        assert result == timestamp_tokens  # Should be unchanged

        # Test that non-timestamp tokens with colons are split
        range_tokens = ['1V:2V']
        result = self.engine.split_vs_tokens_on_colon(range_tokens)
        assert result == ['1V', ':', '2V']

    def test_extract_expressions_edge_cases(self):
        # Test extract_expressions with various edge cases
        result = self.engine.extract_expressions(['A', 'B', 'C'], 'TO')
        assert len(result) == 1  # No separator found

        result = self.engine.extract_expressions(['A', ',', 'B', ',', 'C'])
        assert len(result) == 3  # Comma separated

        result = self.engine.extract_expressions([])
        assert len(result) == 0  # Empty list

    def test_handle_write_invalid_format_chars(self):
        # Test line 443: Invalid format character
        with pytest.raises(ValueError, match="Invalid format"):
            self.engine.handle_write(['WRITE', '%Z', '42'], 1)

    def test_run_line_check_keyword(self):
        # Test line 951: CHECK keyword case
        with mock.patch.object(self.engine, 'handle_check') as mock_check:
            self.engine.run_line("CHECK SPACECRAFT TLM", [], "test.txt", 1)
            mock_check.assert_called_once()

    def test_run_line_clear_keyword(self):
        # Test line 953: CLEAR keyword case
        with mock.patch.object(self.engine, 'handle_clear') as mock_clear:
            self.engine.run_line("CLEAR SCREEN", [], "test.txt", 1)
            mock_clear.assert_called_once()

    def test_run_line_unknown_keyword_with_next(self):
        # Test line 996: Label handling with next
        # This tests the case where we have a label (ends with :)
        result = self.engine.run_line("UNKNOWN_LABEL:", [], "test.txt", 1)
        assert result == 2  # Should increment line number

    def test_handle_check_with_format_f(self):
        # Test line 501: Format F for floating point
        with mock.patch('builtins.print') as mock_print:
            self.engine.handle_check(['CHECK', '%F', '3.14159'], 1)
            # Should format with 6 decimal places for formatted value, original for source
            mock_print.assert_called_with("CHECK SUCCESS: 3.14159 = 3.141590")

    def test_handle_cmd_by_clause(self):
        # Test line 553: BY clause handling
        with mock.patch('cstol_script_engine.cmd') as mock_cmd:
            tokens = ['SET', 'TARGET1', 'PARAM1', 'BY', '42']
            self.engine.handle_cmd(tokens, 1)
            mock_cmd.assert_called_once_with("TARGET1", "SET", {"PARAM1": 42})

    def test_handle_cmd_with_clause_non_cmd_verb(self):
        # Test line 580: WITH clause with non-CMD verb
        with mock.patch('cstol_script_engine.cmd') as mock_cmd:
            tokens = ['SET', 'SPACECRAFT', 'WITH', 'PARAM1', '42']
            self.engine.handle_cmd(tokens, 1)
            mock_cmd.assert_called_once_with("SPACECRAFT", "SET", {"PARAM1": 42})

    def test_handle_cmd_no_clauses_non_cmd_verb(self):
        # Test line 591, 593: No clauses with non-CMD verb
        with mock.patch('cstol_script_engine.cmd') as mock_cmd:
            tokens = ['SET', 'TARGET1']
            self.engine.handle_cmd(tokens, 1)
            mock_cmd.assert_called_once_with("TARGET1", "SET", {})

    def test_handle_check_format_missing_lines(self):
        # Test various format-related missing lines
        with mock.patch('builtins.print') as mock_print:
            # Test that we can reach format handling code paths
            self.engine.handle_check(['CHECK', '%D', '42'], 1)
            mock_print.assert_called_with("CHECK SUCCESS: 42 = 42")

    def test_special_variable_edge_cases(self):
        # Test special variable access patterns
        self.engine.variables.set_special_variable('$$NUM', 123)
        result = self.engine.build_python_expression(['$$NUM', '+', '1'])
        assert '123' in result

    def test_handle_escape_no_matching_endloop(self):
        # Test line 653: ESCAPE with missing ENDLOOP
        lines = ["LOOP", "ESCAPE", "SOME CODE"]
        with pytest.raises(ValueError, match="No matching ENDLOOP found"):
            self.engine.handle_escape(['ESCAPE'], lines, 1)

    def test_handle_let_with_item_name_string(self):
        # Test line 732: LET with item name and string result
        with mock.patch('cstol_script_engine.set_tlm') as mock_set_tlm:
            tokens = ['LET', 'SPACECRAFT', 'ITEM1', '=', '"test"']
            self.engine.handle_let(tokens, 1)
            mock_set_tlm.assert_called_with("SPACECRAFT LATEST ITEM1 = 'test'")

    def test_more_error_paths(self):
        # Test invalid format in WRITE
        with pytest.raises(ValueError, match="Invalid format"):
            self.engine.handle_write(['WRITE', '%Q', '42'], 1)  # Q is not valid format

    def test_handle_cmd_no_clauses_cmd_verb(self):
        # Test line 591: No clauses with CMD verb
        with mock.patch('cstol_script_engine.cmd') as mock_cmd:
            tokens = ['CMD', 'TARGET1', 'COMMAND1']
            self.engine.handle_cmd(tokens, 1)
            mock_cmd.assert_called_once_with("TARGET1", "COMMAND1", {})

    def test_label_with_next_statement(self):
        # Test line 996: Label processing that hits 'next' statement
        # This should pass through without error
        result = self.engine.run_line("TEST_LABEL:", [], "test.txt", 1)
        assert result == 2  # Line number + 1

    def test_write_format_error_443(self):
        # Test line 443: Invalid format error in handle_write
        with pytest.raises(ValueError, match="Invalid format %'Z'"):
            self.engine.handle_write(['WRITE', '%Z', '42'], 1)

    def test_complex_error_scenarios(self):
        # Test LET with invalid variable syntax
        with pytest.raises(ValueError, match="Expected '=' after variable name"):
            self.engine.handle_let(['LET', '$VAR', 'WRONG', '42'], 1)

        # Test IF with syntax error (lines 683-684)
        with pytest.raises(ValueError, match="Error evaluating expression"):
            lines = ["IF 1 + +", "ENDIF"]  # Invalid syntax
            self.engine.handle_if(['IF', '1', '+', '+'], lines, 0)

    def test_build_python_expression_tlm_conversion(self):
        # Test the TODO implementation: converting quoted strings to tlm() calls

        # Test "RAW", "TARGET_NAME", "ITEM_NAME" pattern
        tokens = ['RAW', 'SPACECRAFT', 'TEMPERATURE']
        result = self.engine.build_python_expression(tokens)
        expected = 'tlm("SPACECRAFT", "LATEST", "TEMPERATURE", type="RAW")'
        assert result == expected

        # Test "TARGET_NAME", "ITEM_NAME" pattern
        tokens = ['SPACECRAFT', 'PRESSURE']
        result = self.engine.build_python_expression(tokens)
        expected = 'tlm("SPACECRAFT", "LATEST", "PRESSURE")'
        assert result == expected

        # Test mixed patterns don't interfere with each other
        tokens = ['SPACECRAFT', 'TEMP', '+', 'RAW', 'SPACECRAFT', 'PRESS']
        result = self.engine.build_python_expression(tokens)
        expected = 'tlm("SPACECRAFT", "LATEST", "TEMP") + tlm("SPACECRAFT", "LATEST", "PRESS", type="RAW")'
        assert result == expected

    def test_build_python_expression_tlm_no_conversion(self):
        # Test that single quoted strings are not converted
        tokens = ['single_token']
        result = self.engine.build_python_expression(tokens)
        assert result == '"single_token"'

        # Test that already quoted strings work normally
        tokens = ['"already_quoted"']
        result = self.engine.build_python_expression(tokens)
        assert result == '"already_quoted"'

    def test_build_python_expression_radix_types(self):
        tokens = ["O#10"]
        result = self.engine.build_python_expression(tokens)
        assert result == "0o10"

        tokens = ["B#10"]
        result = self.engine.build_python_expression(tokens)
        assert result == "0b10"

        tokens = ["D#10"]
        result = self.engine.build_python_expression(tokens)
        assert result == "10"

        tokens = ["X#10"]
        result = self.engine.build_python_expression(tokens)
        assert result == "0x10"

        tokens = ["H#10"]
        result = self.engine.build_python_expression(tokens)
        assert result == "b'\\x10'"

    def test_eval_function(self):
        tokens = ["EVAL", "(", "print('hello')", ")"]
        result = self.engine.build_python_expression(tokens)
        assert result == "eval ( \"print(\'hello\')\" )"

    def test_get_undefined_local_variable(self):
        tokens = ["$UNDEFINED"]
        with pytest.raises(ValueError, match="Unknown variable: \\$UNDEFINED"):
            result = self.engine.build_python_expression(tokens)

    def test_function_with_parens(self):
        tokens = ["SIN", "+", "1"]
        result = self.engine.build_python_expression(tokens)
        assert result == '"SIN" + 1'

    def test_else_with_nested_if(self):
        tokens = ["ELSE"]
        lines = ["IF 1", "WRITE 1", "ELSE", "IF 2", "WRITE 2", "ENDIF", "ENDIF"]
        result = self.engine.handle_else(tokens, lines, 3)
        assert result == 7

    def test_escape_with_nested_loop(self):
        tokens = ["ESCAPE"]
        lines = ["LOOP", "WRITE 1", "ESCAPE", "LOOP", "WRITE 2", "ENDLOOP", "ENDLOOP"]
        self.engine.variables.loop_stack.append([10, None, 1])
        result = self.engine.handle_escape(tokens, lines, 3)
        assert result == 7

    def test_if_with_nested_if(self):
        tokens = ["IF", "FALSE"]
        lines = ["IF FALSE", "WRITE 1", "IF 2", "WRITE 2", "ENDIF", "ENDIF"]
        result = self.engine.handle_if(tokens, lines, 1)
        assert result == 6

    def test_if_with_nested_else(self):
        tokens = ["IF", "FALSE"]
        lines = ["IF FALSE", "WRITE 1", "IF 2", "WRITE 2", "ELSE", "WRITE 3", "ENDIF", "ENDIF"]
        result = self.engine.handle_if(tokens, lines, 1)
        assert result == 8

    def test_if_with_nested_else_if(self):
        tokens = ["IF", "FALSE"]
        lines = ["IF FALSE", "WRITE 1", "IF 2", "WRITE 2", "ELSEIF 3", "WRITE 3", "ENDIF", "ENDIF"]
        result = self.engine.handle_if(tokens, lines, 1)
        assert result == 8

    def test_if_with_else(self):
        tokens = ["IF", "FALSE"]
        lines = ["IF FALSE", "WRITE 1", "ELSE", "WRITE 2", "ENDIF"]
        result = self.engine.handle_if(tokens, lines, 1)
        assert result == 4

    def test_if_with_else_if(self):
        tokens = ["IF", "FALSE"]
        lines = ["IF FALSE", "WRITE 1", "ELSE IF 3", "WRITE 2", "ENDIF"]
        result = self.engine.handle_if(tokens, lines, 1)
        assert result == 3

    def test_run_line_blank_line(self):
        result = self.engine.run_line("", [], "test.txt", 1)
        assert result == 2

    def test_run_line_label(self):
        result = self.engine.run_line("LABEL:", [], "test.txt", 1)
        assert result == 2