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

import re
import shlex
import datetime
import math
import os
from openc3.script.exceptions import CheckError, StopScriptError
from openc3.script_engines.script_engine import ScriptEngine
from openc3.script import wait, wait_expression, ask_string, clear_screen, clear_all_screens, set_tlm, display_screen, \
    connect_interface, disconnect_interface, send_raw, start, cmd, get_target_file, tlm, ask_string, set_line_delay, step_mode, run_mode

class CstolVariables:
    special_variables = {
        "$$OWLT": 0.0,
        "$$ERROR": "NO_ERROR",
        "$$CHECK_INTERVAL": 1.0,
        "$$STEP_INTERVAL": 0.1,
        "$$CLP_STP_INTERVAL": 0.1,
        "$$CLP_STEP_MODE": "PAUSE",
        "$$STEP_MODE": "PAUSE"
    }

    def __init__(self):
        self.local_variables = {}
        self.if_stack = []
        self.loop_stack = []

    def set_special_variable(self, name, value):
        """
        Sets a special variable, which is a variable that starts with '$$'.
        Special variables are not stored in the local variables dictionary.
        """
        if not name.startswith('$$'):
            raise ValueError(f"Special variable names must start with '$$': {name}")
        self.special_variables[name] = value
        match name.upper():
            case "$$CLP_STP_INTERVAL":
                set_line_delay(value)
                self.special_variables["$$STEP_INTERVAL"] = value
            case "$$STEP_INTERVAL":
                self.set_special_variable("$$CLP_STP_INTERVAL", value)
            case "$$CLP_STEP_MODE":
                mode = str(value).upper()
                if mode == "GO":
                    run_mode()
                    set_line_delay(0)
                elif mode == "PAUSE":
                    run_mode()
                    set_line_delay(self.special_variables["$$STEP_INTERVAL"])
                elif mode == "WAIT":
                    step_mode()
                else:
                    raise ValueError(f"Invalid step mode: {mode}")
                self.special_variables["$$STEP_MODE"] = value
            case "$$STEP_MODE":
                self.set_special_variable("$$CLP_STEP_MODE", value)

    def get_special_variable(self, name):
        """
        Gets a special variable by name.
        Returns None if the variable does not exist.
        """
        if not name.startswith('$$'):
            raise ValueError(f"Special variable names must start with '$$': {name}")
        match name.upper():
            case "$$CURRENT_TIME":
                return datetime.datetime.now(datetime.timezone.utc).timestamp()
            case "$$SC_TIME":
                return datetime.datetime.now(datetime.timezone.utc).timestamp() + self.special_variables["$$OWLT"]
            case "$$LOOP_COUNT":
                if len(self.loop_stack) > 0:
                    return self.loop_stack[-1][2]
                else:
                    return 0

        return self.special_variables.get(name, None)

class CstolScriptEngine(ScriptEngine):

    ONE_YEAR_SECONDS = 31536000

    # Dictionary of known CSTOL tokens - Unknown could be numbers or parts of telemetry names
    KNOWN_TOKENS = {
        'AND': 'and',
        'OR': 'or',
        'XOR': 'xor',
        'NOT': 'not',
        'FOR': '',
        'UNTIL': '',
        'MOD': '%',
        '**': '**',
        '*': '*',
        '(': '(',
        ')': ')',
        '<': '<',
        '>': '>',
        '<=': '<=',
        '>=': '>=',
        '/=': '!=',
        '=': '==',
        '+': '+',
        '-': '-',
        '/': '/',
        'TRUE': 'True',
        'FALSE': 'False',
    }

    FUNCTION_TOKENS = {
        'SIN': 'math.sin',
        'COS': 'math.cos',
        'TAN': 'math.tan',
        'ASIN': 'math.asin',
        'ACOS': 'math.acos',
        'ATAN': 'math.atan',
        'SINH': 'math.sinh',
        'COSH': 'math.cosh',
        'TANH': 'math.tanh',
        'EXP': 'math.exp',
        'LOG': 'math.log',
        'LOG2': 'math.log2',
        'LOG10': 'math.log10',
        'SQRT': 'math.sqrt',
        'EVAL': 'eval',
        'GETENV': 'os.getenv',
    }

    KNOWN_UNITS = [
        'DN',
        'A',
        'C',
        'CM',
        'F',
        'FT',
        'G',
        'GHZ',
        'H',
        'HZ',
        'IN',
        'J',
        'K',
        'KG',
        'KM',
        'KOHM',
        'KV',
        'KW',
        'M',
        'MA',
        'MG',
        'MHZ',
        'MIN',
        'MM',
        'MOHM',
        'MV',
        'MW',
        'OHM',
        'PA',
        'PSI',
        'S',
        'UA',
        'UV',
        'V',
        'W',
    ]

    def __init__(self, running_script):
        super().__init__(running_script)
        self.variables = CstolVariables()
        self.saved_tokens = None

    def cstol_tokenizer(self, s, special_chars='()><+-*/=;,'):
        tokens = self.tokenizer(s, special_chars)

        # Reconstruct full timestamps of the format yyyy/doy-HH:MM:SS into single tokens
        # These get broken up like ["yyyy", "/", "doy", "-", "HH:MM:SS"] by the tokenizer
        reconstructed_tokens = []
        i = 0
        while i < len(tokens):
            # Check if we have a potential timestamp pattern: yyyy/doy-HH:MM:SS
            if (i + 4 < len(tokens) and
                re.match(r'^\d{4}$', tokens[i]) and
                tokens[i + 1] == '/' and
                re.match(r'^\d{1,3}$', tokens[i + 2]) and
                tokens[i + 3] == '-' and
                re.match(r'^\d{1,2}:\d{1,2}:\d{1,2}\.?\d*$', tokens[i + 4])):
                # Reconstruct the full timestamp
                timestamp = tokens[i] + tokens[i + 1] + tokens[i + 2] + tokens[i + 3] + tokens[i + 4]
                reconstructed_tokens.append(timestamp)
                i += 5  # Skip the next 4 tokens since we combined them

            # Check if we have a potential timestamp pattern: /doy-HH:MM:SS
            elif (i + 3 < len(tokens) and
                tokens[i] == '/' and
                re.match(r'^\d{1,3}$', tokens[i + 1]) and
                tokens[i + 2] == '-' and
                re.match(r'^\d{1,2}:\d{1,2}:\d{1,2}\.?\d*$', tokens[i + 3])):
                # Reconstruct the full timestamp
                timestamp = tokens[i] + tokens[i + 1] + tokens[i + 2] + tokens[i + 3]
                reconstructed_tokens.append(timestamp)
                i += 4  # Skip the next 3 tokens since we combined them

            # Check if we have a potential timestamp pattern: yyyy/-HH:MM:SS
            elif (i + 3 < len(tokens) and
                re.match(r'^\d{4}$', tokens[i]) and
                tokens[i + 1] == '/' and
                tokens[i + 2] == '-' and
                re.match(r'^\d{1,2}:\d{1,2}:\d{1,2}\.?\d*$', tokens[i + 3])):
                # Reconstruct the full timestamp
                timestamp = tokens[i] + tokens[i + 1] + tokens[i + 2] + tokens[i + 3]
                reconstructed_tokens.append(timestamp)
                i += 4  # Skip the next 3 tokens since we combined them

            # Check if we have a potential timestamp pattern: yyyy/-HH:MM:SS
            elif (i + 2 < len(tokens) and
                tokens[i] == '/' and
                tokens[i + 1] == '-' and
                re.match(r'^\d{1,2}:\d{1,2}:\d{1,2}\.?\d*$', tokens[i + 2])):
                # Reconstruct the full timestamp
                timestamp = tokens[i] + tokens[i + 1] + tokens[i + 2]
                reconstructed_tokens.append(timestamp)
                i += 3  # Skip the next 2 tokens since we combined them

            else:
                # Recombine multi-part operator tokens
                token = tokens[i]
                if token in self.KNOWN_TOKENS and i + 1 < len(tokens):
                    next_token = tokens[i + 1]
                    if ((token == '*' and next_token == '*') or
                        (token == '<' and next_token == '=') or
                        (token == '>' and next_token == '=') or
                        (token == '/' and next_token == '=')):
                        reconstructed_tokens.append(token + next_token)
                        i += 2 # Skip the next token
                        continue

                reconstructed_tokens.append(token)
                i += 1

        return reconstructed_tokens

    def build_python_expression(self, expression_tokens):
        """
        Builds a Python expression from the provided tokens.

        Needs to handle all the CSTOL operators and syntax, converting them into valid Python syntax.

        Args:
            expression_tokens: List of tokens that form a valid Python expression

        Returns:
            A string representing the Python expression
        """
        final_tokens = []
        previous_number = False
        for index, token in enumerate(expression_tokens):
            # Handle Units
            if previous_number and token.upper() in self.KNOWN_UNITS:
                # Just drop the units
                previous_number = False
                continue
            previous_number = False

            # Handle special variables
            if token.startswith('$$'):
                # Get the actual value of special variable
                value = self.variables.get_special_variable(token)
                if isinstance(value, str):
                    final_tokens.append(f'"{value}"')
                else:
                    final_tokens.append(str(value))
                continue

            # Handle local variables
            if token.startswith('$'):
                # Get the actual value of local variable
                value = self.variables.local_variables.get(token, None)
                if value is None:
                    raise ValueError(f"Unknown variable: {token}")
                if isinstance(value, str):
                    final_tokens.append(f'"{value}"')
                else:
                    final_tokens.append(str(value))
                continue

            # Handle CSTOL operators and convert to Python equivalents
            if token.upper() in self.KNOWN_TOKENS:
                token = self.KNOWN_TOKENS[token.upper()]
                final_tokens.append(token)
                continue

            # Handle CSTOL functions
            if token.upper() in self.FUNCTION_TOKENS:
                # Function tokens must be followed by ( or they will be considered just strings
                if len(expression_tokens) > index + 1 and expression_tokens[index + 1] == '(':
                    token = self.FUNCTION_TOKENS[token.upper()]
                    final_tokens.append(token)
                else:
                    final_tokens.append(f'"{token}"')
                continue

            # Handle timestamps
            timestamp = self.parse_timestamp(token)
            if timestamp is not None:
                final_tokens.append(str(timestamp))
                continue

            # Handle radix notation integers
            matches = re.match(r'^[BODXHbodxh]#\d+$', token)
            if matches is not None:
                match (token[0].upper()):
                    case 'B':
                        final_tokens.append(f'0b{token[2:]}')
                    case 'O':
                        final_tokens.append(f'0o{token[2:]}')
                    case 'D':
                        final_tokens.append(f'{token[2:]}')
                    case 'H':
                        final_tokens.append(str(int(token[2:], 16).to_bytes((len(token[2:]) + 1) // 2, 'big')))
                    case 'X':
                        final_tokens.append(f'0x{token[2:]}')
                previous_number = True
                continue

            # Handle numbers - Remove DN and EUs
            # Use regex to extract the numeric part (including scientific notation)
            # This pattern matches:
            # - Optional sign (+/-)
            # - Digits, optional decimal point and more digits
            # - Optional scientific notation (e/E followed by optional sign and digits)
            # - Ignores any alphabetic characters that follow
            matches = re.match(r'^([+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)', token)
            if matches is not None:
                final_tokens.append(str(matches.group(1)))
                previous_number = True
                continue

            # Handle quoted strings and non-numbers
            if token.startswith('"') and token.endswith('"'):
                # Already quoted with double quotes
                final_tokens.append(token)
            elif token.startswith("'") and token.endswith("'"):
                # Already quoted with single quotes
                final_tokens.append(token)
            else:
                # Non numbers should become quoted strings
                final_tokens.append(f'"{token}"')

        # Second pass: look for sets of double quoted strings and convert to tlm() calls
        processed_tokens = []
        i = 0
        while i < len(final_tokens):
            token = final_tokens[i]

            # Check for "RAW" pattern first: "RAW", "TARGET_NAME", "ITEM_NAME"
            if (token == '"RAW"' and i + 2 < len(final_tokens) and
                final_tokens[i + 1].startswith('"') and final_tokens[i + 1].endswith('"') and
                final_tokens[i + 2].startswith('"') and final_tokens[i + 2].endswith('"')):

                target_name = final_tokens[i + 1][1:-1]  # Remove quotes
                item_name = final_tokens[i + 2][1:-1]    # Remove quotes
                tlm_call = f'tlm("{target_name}", "LATEST", "{item_name}", type="RAW")'
                processed_tokens.append(tlm_call)
                i += 3  # Skip the next 2 tokens

            # Check for regular pattern: "TARGET_NAME", "ITEM_NAME"
            elif (token.startswith('"') and token.endswith('"') and i + 1 < len(final_tokens) and
                  final_tokens[i + 1].startswith('"') and final_tokens[i + 1].endswith('"')):

                target_name = token[1:-1]                    # Remove quotes
                item_name = final_tokens[i + 1][1:-1]        # Remove quotes
                tlm_call = f'tlm("{target_name}", "LATEST", "{item_name}")'
                processed_tokens.append(tlm_call)
                i += 2  # Skip the next token

            else:
                # Keep the original token
                processed_tokens.append(token)
                i += 1

        # Join the processed tokens into a single string
        return ' '.join(processed_tokens)

    # Combined regex pattern to match both formats
    TIMESTAMP_PATTERN = r'(?:(\d{4})?/(\d{1,3})?-)?(\d{0,2}):(\d{0,2}):(\d{1,2}\.?\d*)'

    # Will convert a CSTOL Clock Time or Delta Time into floating point seconds
    def parse_timestamp(self, timestamp, now = None):
        if now is None:
            now = datetime.datetime.now(datetime.timezone.utc)

        matches = re.match(self.TIMESTAMP_PATTERN, timestamp)
        if matches:
            year, day_of_year, hour, minute, second = matches.groups()
            if len(hour) == 0:
                hour = 0
            if len(minute) == 0:
                minute = 0
            result = {
                'hour': int(hour),
                'minute': int(minute),
                'second': float(second)
            }

            # Determine if / was present (meaning a clock time rather than delta time)
            if '/' in timestamp:
                result['clock_time'] = True
            else:
                result['clock_time'] = False

            # Add year and day_of_year if they exist
            if year is not None:
                result['year'] = int(year)
            elif result['clock_time']:
                result['year'] = now.year

            if day_of_year is not None:
                result['day_of_year'] = int(day_of_year)
            elif result['clock_time']:
                result['day_of_year'] = now.timetuple().tm_yday

            # Extract seconds and microseconds from fractional seconds
            total_seconds = result['second']
            seconds = int(total_seconds)
            # Use round to handle floating point precision issues
            microseconds = round((total_seconds - seconds) * 1000000)

            if 'year' in result and 'day_of_year' in result:
                # Create datetime from year and day of year
                base_date = datetime.datetime(
                    year=result['year'],
                    month=1,
                    day=1,
                    tzinfo=datetime.timezone.utc
                ) + datetime.timedelta(days=result['day_of_year'] - 1)

                return datetime.datetime(
                    year=base_date.year,
                    month=base_date.month,
                    day=base_date.day,
                    hour=result['hour'],
                    minute=result['minute'],
                    second=seconds,
                    microsecond=microseconds,
                    tzinfo=datetime.timezone.utc
                ).timestamp()
            else:
                # Delta Time
                return datetime.timedelta(
                    hours=result['hour'],
                    minutes=result['minute'],
                    seconds=seconds,
                    microseconds=microseconds
                ).total_seconds()

        return None

    def flatten(self, xss):
        return [x for xs in xss for x in xs]

    def extract_expressions(self, tokens, seperator=","):
        # Split the tokens into expressions based on seperator
        # This allows for multiple expressions in a single line, separated by commas
        expressions = []
        expression = []
        for token in tokens:
            if token.upper() == seperator:
                expressions.append(expression)
                expression = []
            else:
                expression.append(token)
        if len(expression) > 0:
            expressions.append(expression)
        return expressions

    def split_vs_tokens_on_colon(self, tokens):
        """
        Split tokens on colons for VS clause processing, but preserve timestamps.
        Timestamps (yyyy/doy-HH:MM:SS or HH:MM:SS) should not be split.
        Range expressions like "1V:2V" should be split into ["1V", ":", "2V"].
        Handles both pre-split tokens and tokens that need splitting.
        """
        result = []
        for token in tokens:
            if ':' in token and not re.fullmatch(self.TIMESTAMP_PATTERN, token):
                # Split non-timestamp tokens containing colons
                parts = token.split(':')
                for i, part in enumerate(parts):
                    if i > 0:
                        result.append(':')
                    if part:  # Only add non-empty parts
                        result.append(part)
            else:
                result.append(token)
        return result

    def evaluate_expression(self, expression):
        """
        Evaluates a single CSTOL expression and returns the result.
        The expression can be a variable, a number, or a complex expression.
        """
        # Convert the expression to a Python expression
        python_expression = self.build_python_expression(expression)
        result = None
        try:
            # Evaluate the expression and return the result
            result = eval(python_expression, {'math': math, 'os': os, 'tlm': tlm})
        except Exception as e:
            raise ValueError(f"Error evaluating expression '{python_expression}': {e}")
        return result

    def evaluate_expressions(self, expressions):
        # Convert each expression to a Python expression
        results = []
        for expr in expressions:
            results.append(self.evaluate_expression(expr))

        return results

    def evaluate_tokens(self, tokens):
        # Evaluates each token to clear any possible variables
        results = []
        for token in tokens:
            results.append(self.evaluate_expression([token]))
        return results

    def handle_ask(self, tokens, line_no):
        if len(tokens) != 3:
            raise ValueError(f"Invalid ASK command format at line {line_no}")

        variable = tokens[1]
        question = tokens[2]
        if (question.startswith('"') and question.endswith('"')) or (question.startswith("'") and question.endswith("'")):
            # Remove quotes
            question = question[1:-1]
        answer = ask_string(question)
        if answer is not None:
            if answer[0] == '"' and answer[-1] == '"':
                # Remove quotes and don't uppercase and don't eval
                answer = answer[1:-1]
            else:
                # Tokenize answer
                answer_tokens = self.cstol_tokenizer(answer)

                # Evaluate answer
                answer = self.evaluate_expression(answer_tokens)

                # Uppercase
                if isinstance(answer, str):
                    answer = answer.upper()
            self.variables.local_variables[variable] = answer

    def handle_check(self, tokens, line_no):
        expressions = self.extract_expressions(tokens[1:], ",")
        for expr in expressions:
            format = None
            if expr[0][0] == '%':
                # Format string
                # %X or %x Output in hexadecimal values Value is converted to an integer prior to applying the format
                # %O or %o Output in octal values Value is converted to an integer prior to applying the format
                # %B or %b Output in binary values Value is converted to an integer prior to applying the format
                # %I or %i Output in decimal values Value is converted to an integer prior to applying the format
                # %D or %d Output in decimal values Value is converted to an integer prior to applying the format
                # %F or %f Output in floating point values Default for integer or raw value
                # %E or %e Output in floating point values Default for float or EU value
                format = expr[0][1:].upper()
                if format not in ['X', 'O', 'B', 'I', 'D', 'F', 'E']:
                    raise ValueError(f"Invalid format %'{format}' in CHECK command at line {line_no}")
                if len(expr) < 2:
                    raise ValueError(f"Missing value for format %'{format}' in CHECK command at line {line_no}")
                # Remove format from the expression
                expr = expr[1:]

            # Check for VS
            success = True
            fail_message = None
            source = None
            value = None
            vs_expressions = self.extract_expressions(expr, "VS")
            if len(vs_expressions) > 1:
                source = " ".join(vs_expressions[0])
                value = self.evaluate_expression(vs_expressions[0])
                # First split any non-timestamp tokens containing colons
                vs_tokens = self.split_vs_tokens_on_colon(self.flatten(vs_expressions[1:]))
                colon_expressions = self.extract_expressions(vs_tokens, ":")
                if len(colon_expressions) > 1:
                    # Range check
                    if len(colon_expressions) != 2:
                        raise ValueError(f"Invalid range format at line {line_no}")
                    range_start = self.evaluate_expression(colon_expressions[0])
                    range_end = self.evaluate_expression(colon_expressions[1])
                    if range_start > range_end:
                        raise ValueError(f"Invalid VS range {range_start}:{range_end} at line {line_no}")
                    if (value < range_start) or (value > range_end):
                        success = False
                        fail_message = f"not in range {range_start}:{range_end}"
                else:
                    # Single value check
                    vs_value = self.evaluate_expression(colon_expressions[0])
                    if value != vs_value:
                        success = False
                        fail_message = f"not equal to {vs_value}"
            else:
                 # No VS - Just a print check
                source = " ".join(expr)
                value = self.evaluate_expression(expr)

            formatted_value = None
            if format is None:
                formatted_value = str(value)
            elif format in ['X', 'O', 'B', 'I', 'D']:
                # Convert to integer
                value = int(value)
                if format == 'X':
                    formatted_value = (f"{value:X}")
                elif format == 'O':
                    formatted_value = (f"{value:o}")
                elif format == 'B':
                    formatted_value = (f"{value:b}")
                elif format in ['I', 'D']:
                    formatted_value = str(value)
            elif format in ['F', 'E']:
                # Convert to float
                value = float(value)
                if format == 'F':
                    formatted_value = f"{value:.6f}"
                elif format == 'E':
                    formatted_value = f"{value:.6e}"

            if success:
                print(f"CHECK SUCCESS: {source} = {formatted_value}")
            else:
                message = f"CHECK FAILED: {source} = {formatted_value} ({fail_message})"
                print(message)
                raise CheckError(message)

    def handle_clear(self, tokens, line_no):
        """ Only handles displays """
        if tokens[1].upper() == 'ALL':
            clear_all_screens()
        else:
            screen_name = tokens[1]
            if (screen_name.startswith('"') and screen_name.endswith('"')) or (screen_name.startswith("'") and screen_name.endswith("'")):
                # Remove quotes
                screen_name = screen_name[1:-1]
            clear_screen(*screen_name.split())

    def handle_cmd(self, tokens, line_no):
        if tokens[0].upper() == 'NOW':
            # Drop NOW
            tokens = tokens[1:]

        verb = tokens[0].upper()
        tokens = tokens[1:]
        match verb:
            case "ACTIVATE" | "ARM" | "BOOT" | "CHANGE" | "CLOSE" | "DISABLE" | "DISARM" | "DRIVE" | \
                "DUMP" | "ENABLE" | "FIRE" | "FLYBACK" | "FORCE" | "GET" | "HALT" | "HOLD" | "IGNORE" | "INITIATE" | \
                "MOVE" | "NOW" | "OPEN" | "PASS" | "PERFORM" | "RESET" | "SELECT" | "SET" | "SLEW" | "STEP" | "TEST" | \
                "TOGGLE" | "TURN" | "USE":
                # Handle all the weird verbs
                if verb == "TURN" or verb == "FORCE":
                    # Expect ON or OFF to follow
                    if tokens[0].upper() == 'ON' or tokens[0].upper() == 'OFF':
                        verb = verb + tokens[0].upper()
                        tokens = tokens[1:]
                    else:
                        raise ValueError(f"TURN and FORCE must be followed by ON or OFF at line {line_no}")
            case "CMD":
                pass

        # Now we need to discover any TO, BY, FROM, WITH clauses
        target_name = None
        cmd_name = None
        args = {}
        single_value_expressions = None
        to_expressions = self.extract_expressions(tokens, "TO")
        by_expressions = self.extract_expressions(tokens, "BY")
        from_expressions = self.extract_expressions(tokens, "FROM")
        with_expressions = self.extract_expressions(tokens, "WITH")
        if len(to_expressions) > 1:
            single_value_expressions = to_expressions
        elif len(by_expressions) > 1:
            single_value_expressions = by_expressions
        elif len(from_expressions) > 1:
            single_value_expressions = from_expressions

        if single_value_expressions is not None:
            # TO, BY, or FROM
            value = self.evaluate_expression(single_value_expressions[1])
            pretokens = self.evaluate_tokens(single_value_expressions[0])
            if len(pretokens) == 1:
                target_name = pretokens[0]
                cmd_name = verb
                args["VALUE"] = value
            elif len(pretokens) == 2:
                target_name = pretokens[0]
                if verb == "CMD":
                    cmd_name = pretokens[1]
                    args["VALUE"] = value
                else:
                    cmd_name = verb
                    args[pretokens[1]] = value
            else:
                raise ValueError(f"Malformed TO cmd at line {line_no}")
        elif len(with_expressions) > 1:
            # WITH
            pretokens = self.evaluate_tokens(with_expressions[0])
            target_name = pretokens[0]
            if verb == "CMD":
                cmd_name = pretokens[1]
            else:
                cmd_name = verb
            expressions = self.extract_expressions(with_expressions[1])
            for expr in expressions:
                arg_name = self.evaluate_tokens([expr[0]])[0]
                value = self.evaluate_expression(expr[1:])
                args[arg_name] = value
        else:
            # No clauses
            tokens = self.evaluate_tokens(tokens)
            target_name = tokens[0]
            if verb == "CMD":
                cmd_name = tokens[1]
            else:
                cmd_name = verb

        cmd(target_name, cmd_name, args)

    def handle_declare(self, tokens, line_no):
        """ We ignore ranges and allowed value lists """
        # DECLARE mode variable-name = default-value [range value-list]
        mode = tokens[1].upper()
        if mode not in ['INPUT', 'VARIABLE', 'CONSTANT']:
            raise ValueError(f"Invalid mode '{mode}' in DECLARE command at line {line_no}")
        variable_name = tokens[2]
        if not variable_name.startswith('$'):
            raise ValueError(f"Variable name must start with '$' in DECLARE command at line {line_no}")
        equals = tokens[3]
        if equals != '=':
            raise ValueError(f"Expected '=' after variable name in DECLARE command at line {line_no}")
        #default_value = self.token_to_value(tokens[4])
        default_value = self.evaluate_tokens([tokens[4]])[0]
        self.variables.local_variables[variable_name] = default_value

    def handle_display(self, tokens, line_no):
        screen_name = tokens[1]
        if (screen_name.startswith('"') and screen_name.endswith('"')) or (screen_name.startswith("'") and screen_name.endswith("'")):
            # Remove quotes
            screen_name = screen_name[1:-1]
        display_screen(*screen_name.split())

    def handle_else(self, tokens, lines, line_no):
        goto_endif = False
        if len(tokens) > 1:
            # ELSE IF is tricky - We can hit these after a successful IF, or an unsuccessful IF
            # The if_stack keeps track if an earlier if was successful and its value will determine if we
            # execute the ELSEIF or just goto the next ENDIF
            current_if = False
            if len(self.variables.if_stack) > 0:
                current_if = self.variables.if_stack[-1]
            if tokens[0].upper() == 'ELSEIF':
                if current_if:
                    goto_endif = True
                else:
                    return self.handle_if(tokens, lines, line_no)
            elif (tokens[0].upper() == 'ELSE' and tokens[1].upper() == 'IF'):
                if current_if:
                    goto_endif = True
                else:
                    return self.handle_if(tokens[1:], lines, line_no)

        if goto_endif or (len(tokens) == 1 and tokens[0].upper() == 'ELSE'):
            # The only way we ever hit an ELSE is if we were in a successful block beforehand
            # Therefore goto the ENDIF
            self.variables.if_stack[-1] = True
            depth = 1
            for i in range(line_no, len(lines)):
                next_line = lines[i].strip().upper()
                if next_line.startswith('IF '):
                    depth += 1
                elif next_line.startswith('ENDIF') or next_line.startswith('END IF'):
                    depth -= 1
                    if depth == 0:
                        return i + 1
            raise ValueError(f"No matching ENDIF for ELSE command at line {line_no}")

        raise ValueError(f"handle_else called with unexpected tokens at line {line_no}")

    def handle_end(self, tokens, line_no):
        if len(tokens) == 1 and tokens[0].upper() == 'END':
            raise ValueError(f"Unexpected END command at line {line_no}, expected ENDIF, ENDLOOP, ENDMACRO, or ENDPROC")
        elif (len(tokens) == 1 and tokens[0].upper() == 'ENDIF') or (tokens[0].upper() == 'END' and tokens[1].upper() == 'IF'):
            # END IF pops the IF stack
            self.variables.if_stack.pop()
            pass
        elif (len(tokens) == 1 and tokens[0].upper() == 'ENDLOOP') or (tokens[0].upper() == 'END' and tokens[1].upper() == 'LOOP'):
            if len(self.variables.loop_stack) > 0:
                loop_info = self.variables.loop_stack[-1]
                loop_info[2] += 1
                if loop_info[1] is not None:
                    # Counted loop, decrement the count
                    loop_info[1] -= 1
                    if loop_info[1] > 0:
                        return loop_info[0]
                    else:
                        self.variables.loop_stack.pop()
                        return line_no + 1  # Continue to the next line
                else:
                    # Infinite loop, just continue to the start of the loop
                    return loop_info[0]
        return line_no + 1

    def handle_escape(self, _tokens, lines, line_no):
        # Find the matching ENDLOOP
        depth = 1
        for i in range(line_no, len(lines)):
            next_line = lines[i].strip()
            if next_line.startswith('LOOP'):
                depth += 1
            elif next_line.startswith('END LOOP') or next_line.startswith('ENDLOOP'):
                depth -= 1
                if depth == 0:
                    if len(self.variables.loop_stack) > 0:
                        self.variables.loop_stack.pop()
                    return i + 1
        raise ValueError(f"No matching ENDLOOP found for ESCAPE command at line {line_no}")

    def handle_go(self, tokens, lines, line_no):
        if tokens[0].upper() == 'GOTO' or (len(tokens) > 1 and tokens[0].upper() == 'GO' and tokens[1].upper() == 'TO'):
            if (tokens[0].upper() == 'GOTO' and len(tokens) < 2) or (tokens[0].upper() == 'GO' and tokens[1].upper() != 'TO' and len(tokens) < 3):
                raise ValueError(f"Invalid GOTO command format at line {line_no}")
            label = None
            if tokens[0].upper() == 'GOTO':
                label = (tokens[1] + ':').upper()
            else:
                label = (tokens[2] + ':').upper()
            # Find the label in the lines
            for i in range(1, len(lines)):
                next_line = lines[i - 1].strip().upper()
                if next_line.startswith(label):
                    return i
            raise ValueError(f"Label '{label}' not found in GOTO command at line {line_no}")

    def handle_if(self, tokens, lines, line_no):
        expression_tokens = tokens[1:]
        result = None
        try:
            # Evaluate the expression and store the result in the variable
            result = self.evaluate_expression(expression_tokens)
        except Exception as e:
            raise ValueError(f"Error evaluating expression '{expression_tokens}' in IF command at line {line_no}: {e}")

        if result:
            # Mark if as handled
            self.variables.if_stack[-1] = True
            return line_no + 1  # Continue to the next line if the condition is true
        # If the condition is false, skip to the next ENDIF or ELSE
        else:
            # Find the matching ENDIF or ELSE
            depth = 1
            for i in range(line_no, len(lines)):
                next_line = lines[i].strip().upper()
                if next_line.startswith('IF '):
                    depth += 1
                elif next_line.startswith('ENDIF') or next_line.startswith('END IF'):
                    depth -= 1
                    if depth == 0:
                        return i + 1
                elif next_line.startswith('ELSE'):
                    if next_line.startswith('ELSEIF') or next_line.startswith('ELSE IF'):
                        # Continue to the ELSE IF
                        if depth == 1:
                            return i + 1
                    else:
                        # Regular ELSE - Continue to line after
                        if depth == 1:
                            return i + 2

        raise ValueError(f"No matching ENDIF or ELSE found for IF command at line {line_no}")

    def handle_let(self, tokens, line_no):
        # LET variable = expression
        if len(tokens) < 4:
            raise ValueError(f"Invalid LET command format at line {line_no}")
        variable_name = tokens[1]
        item_name = None
        expression_tokens = None
        if not variable_name.startswith('$'):
            if tokens[2] != '=':
                # Global variable for set_tlm
                item_name = tokens[2]
                expression_tokens = tokens[4:]
            else:
                raise ValueError(f"Non-global variable name must start with '$' in LET command at line {line_no}")
        elif tokens[2] == '=':
            # Local or Special variable
            expression_tokens = tokens[3:]
        else:
            raise ValueError(f"Expected '=' after variable name in LET command at line {line_no}")

        result = None
        try:
            # Evaluate the expression and store the result in the variable
            result = self.evaluate_expression(expression_tokens)
        except Exception as e:
            raise ValueError(f"Error evaluating expression '{expression_tokens}' in LET command at line {line_no}: {e}")

        if item_name:
            if isinstance(result, str):
                set_tlm(f"{variable_name} LATEST {item_name} = '{result}'")
            else:
                set_tlm(f"{variable_name} LATEST {item_name} = {result}")
        elif variable_name.startswith('$$'):
            # Special variable
            self.variables.set_special_variable(variable_name, result)
        else:
            # Local variable
            self.variables.local_variables[variable_name] = result

    def handle_load(self, tokens, line_no):
        # LOAD external-element-name AT location FROM file-name
        expressions = self.extract_expressions(tokens[1:], "AT")
        if len(expressions) != 2:
            raise ValueError(f"Invalid LOAD command format at line {line_no}")
        interface_name = expressions[0]
        expressions = self.extract_expressions(self.flatten(expressions[1:]), "FROM")
        if len(expressions) != 2:
            raise ValueError(f"Invalid LOAD command format at line {line_no}")
        location = expressions[0]
        filename = expressions[1]
        results = self.evaluate_expressions([interface_name, location, filename])
        interface_name = results[0]
        location = results[1]
        filename = results[2]
        file = get_target_file(filename)
        data = file.read()
        file.close()
        send_raw(interface_name, data)

    def handle_loop(self, tokens, line_no):
        if len(tokens) == 1:
            # Infinite loop
            self.variables.loop_stack.append([line_no + 1, None, 1])
            return line_no + 1  # Continue to the next line
        elif len(tokens) == 2:
            # Counted loop
            count = int(tokens[1])
            self.variables.loop_stack.append([line_no + 1, count, 1])
            return line_no + 1  # Continue to the next line
        else:
            raise ValueError(f"Invalid LOOP command format at line {line_no}")

    def handle_proc(self, tokens, line_no):
        # tokens[1] is proc name
        if len(tokens) > 2:
            # Variables
            index = 0
            for token in tokens[2:]:
                if token == ',':
                    continue
                elif token.startswith('$'):
                    self.variables.local_variables[token] = os.getenv(f"CSTOL_ARG_{index}")
                    index += 1
                else:
                    raise ValueError(f"Invalid variable '{token}' in PROC command at line {line_no}")

    def handle_return(self, tokens, lines, line_no):
        if len(tokens) > 1:
            if tokens[1].upper() == 'ALL':
                raise StopScriptError
        return (len(lines) + 1)

    def handle_run(self, tokens, line_no):
        if len(tokens) < 2:
            raise ValueError(f"Invalid RUN command format at line {line_no}")
        script = tokens[1]
        if len(tokens) > 2:
            expressions = self.extract_expressions(tokens[2:], ",")
            results = self.evaluate_expressions(expressions)
            string_results = [('"' + str(result) + '"') for result in results]
            string_results.insert(0, script)
            script = ' '.join(string_results)
        print(f"Running system call: {script}")
        os.system(script)

    def handle_send(self, tokens, line_no):
        # SEND bit-pattern-command TO external-element-name
        # COSMOS implementation uses interface name instead of external-element-name
        expressions = self.extract_expressions(tokens[1:], "TO")
        if len(expressions) != 2:
            raise ValueError(f"Invalid SEND command format at line {line_no}")
        results = self.evaluate_expressions(expressions)
        data = results[0]
        interface_name = results[1]
        send_raw(interface_name, data)

    def handle_start(self, tokens, line_no):
        # START proc-name [argument-list]
        proc_name = tokens[1]

        if (proc_name.startswith('"') and proc_name.endswith('"')) or (proc_name.startswith("'") and proc_name.endswith("'")):
            # Remove quotes
            proc_name = proc_name[1:-1]

        args = []
        if len(tokens) > 2:
            # Handle argument list
            expressions = self.extract_expressions(tokens[2:], ",")
            results = self.evaluate_expressions(expressions)
            args = [str(result) for result in results]
            for index, arg in enumerate(args):
                # Set the environment variable for the argument
                os.environ[f"CSTOL_ARG_{index}"] = arg
        start(proc_name, bind_variables=False)

    def handle_switch(self, tokens, line_no):
        action = tokens[1].upper()
        if action not in ['ON', 'OFF']:
            raise ValueError(f"Invalid SWITCH action '{action}' at line {line_no}")
        interface_name = tokens[2]
        if action == 'ON':
            connect_interface(interface_name)
        elif action == 'OFF':
            disconnect_interface(interface_name)

    def handle_wait(self, tokens, line_no):
        if len(tokens) == 1:
            # Indefinite wait
            wait()
        elif len(tokens) == 2:
            # Timestamp wait - Still need to handle a possible expression like a variable
            seconds = self.evaluate_expression([tokens[1]])
            if isinstance(seconds, (int, float, complex)) and not isinstance(seconds, bool):
                if seconds > self.ONE_YEAR_SECONDS:
                    now = datetime.datetime.now().timestamp()
                    seconds = seconds - now
                    if seconds < 0:
                        seconds = 0.0
                wait(seconds)
            else:
                raise ValueError(f"Invalid timestamp format at line {line_no}")
        else:
            # Conditional expression wait
            expressions = self.extract_expressions(tokens[1:], seperator="OR")
            python_expression = self.build_python_expression(expressions[0])
            if len(expressions) > 1:
                # Timeout given with "OR FOR" or "OR UNTIL"
                seconds = self.evaluate_expression(expressions[1][1:]) # Drop assumed FOR or UNTIL token
                if isinstance(seconds, (int, float, complex)) and not isinstance(seconds, bool):
                    if seconds > self.ONE_YEAR_SECONDS:
                        now = datetime.datetime.now().timestamp()
                        seconds = seconds - now
                        if seconds < 0:
                            seconds = 0.0
                    result = wait_expression(python_expression, seconds, self.variables.get_special_variable("$$CHECK_INTERVAL"), globals={'math': math, 'os': os, 'tlm': tlm})
                    if result:
                        self.variables.set_special_variable("$$ERROR", "NO_ERROR")
                    else:
                        self.variables.set_special_variable("$$ERROR", "TIME_OUT")
                else:
                    raise ValueError(f"Invalid timestamp format at line {line_no}")
            else:
                result = wait_expression(python_expression, 1000000000, self.variables.get_special_variable("$$CHECK_INTERVAL"), globals={'math': math, 'os': os, 'tlm': tlm}) # Effective infinite wait
                if result:
                    self.variables.set_special_variable("$$ERROR", "NO_ERROR")
                else:
                    self.variables.set_special_variable("$$ERROR", "TIME_OUT")

    def handle_write(self, tokens, line_no):
        expressions = self.extract_expressions(tokens[1:], ",")
        results = []
        for expr in expressions:
            result = ''
            if expr[0][0] == '%':
                # Format string
                # %X or %x Output in hexadecimal values Value is converted to an integer prior to applying the format
                # %O or %o Output in octal values Value is converted to an integer prior to applying the format
                # %B or %b Output in binary values Value is converted to an integer prior to applying the format
                # %I or %i Output in decimal values Value is converted to an integer prior to applying the format
                # %D or %d Output in decimal values Value is converted to an integer prior to applying the format
                # %F or %f Output in floating point values Default for integer or raw value
                # %E or %e Output in floating point values Default for float or EU value
                format = expr[0][1:].upper()
                if format not in ['X', 'O', 'B', 'I', 'D', 'F', 'E']:
                    raise ValueError(f"Invalid format %'{format}' in WRITE command at line {line_no}")
                if len(expr) < 2:
                    raise ValueError(f"Missing value for format %'{format}' in WRITE command at line {line_no}")
                value = self.evaluate_expression(expr[1:])
                if format in ['X', 'O', 'B', 'I', 'D']:
                    # Convert to integer
                    value = int(value)
                    if format == 'X':
                        result = (f"{value:X}")
                    elif format == 'O':
                        result = (f"{value:o}")
                    elif format == 'B':
                        result = (f"{value:b}")
                    elif format in ['I', 'D']:
                        result = str(value)
                elif format in ['F', 'E']:
                    # Convert to float
                    value = float(value)
                    if format == 'F':
                        result = f"{value:.6f}"
                    elif format == 'E':
                        result = f"{value:.6e}"
            else:
                result = str(self.evaluate_expression(expr))
            results.append(result)
        # Join the results with spaces
        output = ' '.join(results)
        print(output)

    def run_text(self, text, filename = None, line_no = 1, end_line_no = None, bind_variables = False):
        saved_variables = self.variables
        try:
            if not bind_variables:
                self.variables = CstolVariables()
            super().run_text(text, filename, line_no, end_line_no, bind_variables)
        finally:
            self.variables = saved_variables

    # Override this method in the subclass to implement the script engine
    def run_line(self, line, lines, filename, line_no):
        tokens = self.cstol_tokenizer(line)

        # Skip completely blank lines
        if len(tokens) == 0:
            return line_no + 1

        # Handle continuation lines
        if self.saved_tokens:
            tokens = self.saved_tokens + tokens
            self.saved_tokens = None
        if tokens[-1] == '&':
            self.saved_tokens = tokens[:-1] # Everything before the '&' is saved for the next line
            return line_no + 1  # Skip to the next line

        # Remove any trailing comments
        if ';' in tokens:
            comment_index = tokens.index(';')
            tokens = tokens[:comment_index]

        if len(tokens) != 0:
            keyword = tokens[0].upper()

            # Handle labels
            if keyword.endswith(':'):
                if len(tokens) > 1:
                    tokens = tokens[1:]
                    keyword = tokens[0].upper()
                else:
                    return line_no + 1

            match keyword:
                case "ASK":
                    self.handle_ask(tokens, line_no)
                case "BEGIN":
                     pass
                case "CANCEL" | "CHECKPOINT" | "COMMIT" | "COMPILE" | "CSTOL" | "DECOMPILE" | "DEFINE" | "DELETE" | \
                    "FLUSH" | "INSERT" | "LOCK" | "MACRO" | "RECORD" | "REPORT" | "RESTORE" | "RETREIVE" | "RETRY" | \
                    "SHOW" | "SNAP" | "STOP" | "UNDEFINE" | "UNLOCK" | "UPDATE" | "ROUTE":
                    # These keywords are noops for this CSTOL script engine
                    print(f"Ignoring Unsupported Keyword: {keyword}")
                case "CHECK":
                    self.handle_check(tokens, line_no)
                case "CLEAR":
                    self.handle_clear(tokens, line_no)
                case "ACTIVATE" | "ARM" | "BOOT" | "CHANGE" | "CLOSE" | "CMD" | "DISABLE" | "DISARM" | "DRIVE" | \
                    "DUMP" | "ENABLE" | "FIRE" | "FLYBACK" | "FORCE" | "GET" | "HALT" | "HOLD" | "IGNORE" | "INITIATE" | \
                    "MOVE" | "NOW" | "OPEN" | "PASS" | "PERFORM" | "RESET" | "SELECT" | "SET" | "SLEW" | "STEP" | "TEST" | \
                    "TOGGLE" | "TURN" | "USE":
                    self.handle_cmd(tokens, line_no)
                case "DECLARE":
                    self.handle_declare(tokens, line_no)
                case "DISPLAY":
                    self.handle_display(tokens, line_no)
                case "ELSE" | "ELSEIF":
                    return self.handle_else(tokens, lines, line_no)
                case "END" | "ENDIF" | "ENDLOOP" | "ENDMACRO" | "ENDPROC":
                    return self.handle_end(tokens, line_no)
                case "ESCAPE":
                    return self.handle_escape(tokens, lines, line_no)
                case "GO" | "GOTO":
                    return self.handle_go(tokens, lines, line_no)
                case "IF":
                    # Regular IF starts an if stack
                    self.variables.if_stack.append(False)
                    return self.handle_if(tokens, lines, line_no)
                case "LET":
                    self.handle_let(tokens, line_no)
                case "LOAD":
                    self.handle_load(tokens, line_no)
                case "LOOP":
                    self.handle_loop(tokens, line_no)
                case "PROC":
                    self.handle_proc(tokens, line_no)
                case "RETURN":
                    return self.handle_return(tokens, lines, line_no)
                case "RUN":
                    self.handle_run(tokens, line_no)
                case "SEND":
                    self.handle_send(tokens, line_no)
                case "START":
                    self.handle_start(tokens, line_no)
                case "SWITCH":
                    self.handle_switch(tokens, line_no)
                case "WAIT":
                    self.handle_wait(tokens, line_no)
                case "WRITE":
                    self.handle_write(tokens, line_no)
                case _:
                    raise ValueError(f"Unknown keyword '{keyword}' at line {line_no}")

        return line_no + 1