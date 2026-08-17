## OpenC3 CSTOL Script Engine Plugin

CSTOL language originally developed by the University of Colorado / LASP.

This plugin provides a CSTOL script engine that allows COSMOS ScriptRunner to execute CSTOL scripts.

### Expression Processing Notes and Differences from the CSTOL Spec

1. Both single and double quotes are supported (original CSTOL only had double quotes)
2. DN and EU Units are dropped and have no effect on anything
3. Global variables (telemetry points) always use the LATEST packet name in COSMOS
4. AVERAGED and SMOOTHED are not supported
5. There are no line length limitations

### Supported Special Variables

| Name               | Discussion                                                                                     |
| ------------------ | ---------------------------------------------------------------------------------------------- |
| $$CURRENT_TIME     | Supported. Returns a floating point seconds from epoch value to interpreted Python expressions |
| $$OWLT             | Supported. Defaults to 0.0                                                                     |
| $$SC_TIME          | Supported. Equals $$CURRENT_TIME + $$OWLT                                                      |
| $$ERROR            | Supported. Defaults to "NO_ERROR"                                                              |
| $$CHECK_INTERVAL   | Supported. Defaults to 1.0                                                                     |
| $$CLP_STP_INTERVAL | Supported. Note: Default value is COSMOS default of 0.1 instead of 1                           |
| $$STEP_INTERVAL    | Supported. Note: Default value is COSMOS default of 0.1 instead of 1                           |
| $$CLP_STEP_MODE    | Supported. Note: Default value in COSMOS is PAUSE instead of GO                                |
| $$STEP_MODE        | Supported. Note: Default value in COSMOS is PAUSE instead of GO                                |
| $$LOOP_COUNT       | Supported. Counts up from 1 for each loop iteration. Equals 0 outside of loops                 |

### Not Supported Special Variables

| Name               | Discussion                                                                                        |
| ------------------ | ------------------------------------------------------------------------------------------------- |
| $$GBL_COMMAND_MODE | Not supported. Could potentially make use of COSMOS "disconnect" mode                             |
| $$COMMAND_ECHO     | Not supported. Commands are always printed out. Could potentially affect cmd(log_message)         |
| $$LIMITS_WAIT      | Not supported. Would require adding a thread to monitor limits events and pause the script.       |
| $$LIMITS_MODE      | Not supported. Will not be supported as disabling all limits monitoring is not a desired feature. |
| $$STATES_MODE      | Not supported. Will not be supported as disabling all states monitoring is not a desired feature. |
| $$CEV_MODE         | Not supported. Could potentially affect cmd(validate)                                             |
| $$UED_MODE         | Not supported. Probably will not be supported as this isn't a COSMOS feature                      |
| $$PRECHECK_MODE    | Not supported. Could potentially affect cmd(validate)                                             |
| $$POSTCHECK_MODE   | Not supported. Could potentially affect cmd(validate)                                             |
| $$STALE_CHECK      | Not supported. Staleness is a client side concept in COSMOS                                       |
| $$STALE_CHECK_INT  | Not supported. Staleness is a client side concept in COSMOS                                       |
| $$ALLOW_STALE      | Not supported. Staleness is a client side concept in COSMOS                                       |
| $$COMPILER_OUTPUT  | Not supported. Doesn't make sense in COSMOS                                                       |
| $$COMMAND_MODE     | Not supported. Could potentially make use of COSMOS "disconnect" mode                             |
| $$CLP_LOG_INPUT    | Not supported.                                                                                    |
| $$LOG_INPUT        | Not supported.                                                                                    |
| $$TIME_STAMP       | Not supported.                                                                                    |
| $$CMD_STRING2STATE | Not supported.                                                                                    |

### Supported CSTOL Keywords

| Keyword  | Discussion                                                                                                                       |
| -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| ASK      | Fully supported                                                                                                                  |
| BEGIN    | Has no effect                                                                                                                    |
| CHECK    | Fully supported                                                                                                                  |
| CLEAR    | Uses COSMOS screen names as quoted arguments like "INST ADCS". CLEAR ALL only clears screens, other page types are not supported |
| DECLARE  | Declare is implemented to handle all types the same. Ranges and value lists are ignored                                          |
| DISPLAY  | Uses COSMOS screen names as quoted arguments like "INST ADCS". TO and AT are not supported                                       |
| ELSE     | Fully supported                                                                                                                  |
| ELSEIF   | Fully supported                                                                                                                  |
| END      | Fully supported                                                                                                                  |
| ENDIF    | Fully supported                                                                                                                  |
| ENDLOOP  | Fully supported                                                                                                                  |
| ENDMACRO | Ignored                                                                                                                          |
| ENDPROC  | Ignored                                                                                                                          |
| ESCAPE   | Fully supported                                                                                                                  |
| GOTO     | Fully supported                                                                                                                  |
| IF       | Fully supported                                                                                                                  |
| LET      | Fully supported, but typing checks and ranges are not implemented                                                                |
| LOAD     | Takes an interface name instead of a target name to load data to                                                                 |
| LOOP     | Fully supported                                                                                                                  |
| PROC     | Fully supported                                                                                                                  |
| RETURN   | Fully supported                                                                                                                  |
| RUN      | Fully supported - shells out in the Script Runner container                                                                      |
| SEND     | Takes an interface name instead of a target name to send data to. SEND MESSAGE is not supported.                                 |
| START    | Fully supported. Procedures must be specified with COSMOS paths ie. TARGET/procedures/myproc.prc                                 |
| SWITCH   | Connect or disconnect COSMOS interfaces. Uses interface names. SWITCH RECORDING not supported                                    |
| WAIT     | Fully supported. WAIT AT (breakpoints) are handled through the ScriptRunner API and GUI. WAIT FOR is not supported               |
| WRITE    | Fully supported                                                                                                                  |

The following CSTOL command keywords are supported:

- ACTIVATE
- ARM
- BOOT
- CHANGE
- CLOSE
- CMD
- DISABLE
- DISARM
- DRIVE
- DUMP
- ENABLE
- FIRE
- FLYBACK
- FORCE
- GET
- HALT
- HOLD
- IGNORE
- INITIATE
- MOVE
- NOW
- OPEN
- PASS
- PERFORM
- RESET
- SELECT
- SET
- SLEW
- STEP
- TEST
- TOGGLE
- TURN
- USE

Commands use the command keyword as the expected name of the command. For example `TEST INST` become `cmd("INST TEST")` in COSMOS.

Commands with two words like `TURN ON` remove spaces in the expected command names. `TURN ON INST` becomes `cmd("INST TURNON")` in COSMOS.

The CMD keyword is special in that it expects an argument after the external element to be the command name. `CMD INST TEST with ARG1 1, ARG2 2` becomes `cmd("INST TEST with ARG1 1, ARG2 2")`.

Other command keywords assume a word after the external element is an argument name that should be given a value by a following clause. ` SET INST TEMP TO 10`` becomes  `cmd("INST SET with TEMP 10")```.

If no argument name is given the argument name is assumed to be "VALUE". `SET INST BY 10` becomes `cmd("INST SET with VALUE 10")`.

NOW is supported and ignored.

The following CSTOL keywords are not supported and will simply print a warning:

| Keyword    | Discussion                                                                                             |
| ---------- | ------------------------------------------------------------------------------------------------------ |
| CANCEL     | Commands cannot be canceled in COSMOS                                                                  |
| CHECKPOINT | CSTOL Database is not applicable to COSMOS                                                             |
| COMMIT     | CSTOL Database is not applicable to COSMOS                                                             |
| COMPILE    | CSTOL procedures in Script Runner are evaluated line by line and not compiled                          |
| CSTOL      | Terminating an OASIS-CC session does not make sense in COSMOS.                                         |
| DECOMPILE  | CSTOL is not compiled in COSMOS                                                                        |
| DEFINE     | Macros are not supported                                                                               |
| DELETE     | CSTOL Database is not applicable to COSMOS                                                             |
| FLUSH      | Commands aren't queued in COSMOS                                                                       |
| GO         | Handled through ScriptRunner APIs / Buttons, not through a keyword                                     |
| INSERT     | CSTOL Database is not applicable to COSMOS                                                             |
| LOCK       | CSTOL Database is not applicable to COSMOS                                                             |
| MACRO      | Macros are not supported                                                                               |
| MESSAGE    | Not Supported                                                                                          |
| RECORD     | COSMOS is always logging and cannot be disabled                                                        |
| REPORT     | CSTOL Database is not applicable to COSMOS                                                             |
| RESTORE    | CSTOL Database is not applicable to COSMOS                                                             |
| RETRIEVE   | Playback from files is not supported                                                                   |
| RETRY      | Command retry is not supported, through retrying failed lines is supported through the API and buttons |
| ROUTE      | Not implemented, COSMOS does not have Sub-CLP. Could potentially do map_target_to_interface.           |
| SHOW       | COSMOS does not have CLPs                                                                              |
| SNAP       | Screenshots are not supported                                                                          |
| STOP       | Logging cannot be disabled. Replay is not supported. Sub-CLPs are not supported                        |
| UNDEFINE   | Macros are not supported                                                                               |
| UNLOCK     | CSTOL Database is not applicable to COSMOS                                                             |
| UPDATE     | CSTOL Database is not applicable to COSMOS                                                             |

## Getting Started

1.  At the Administrator Console - Plugins, upload the openc3-cosmos-script-engine-cstol.gem file

## Development

This project uses:

- **uv** for dependency management and locking
- **pytest** for testing
- **ruff** for linting and formatting
- **ty** for static type checking
- **just** for task automation

All Python tooling is configured in `pyproject.toml`, and dependency versions are
pinned in `uv.lock`. Install the development environment with:

```bash
uv sync --group dev
```

Note that `openc3` is a development-only dependency. At runtime COSMOS provides it,
so the plugin declares no runtime dependencies of its own.

### Quick Start with Just

This project uses [just](https://github.com/casey/just) as a command runner. To see
all available commands:

```bash
just --list
```

Common commands:

```bash
# Run all checks (lint, format check, type check, tests)
just check

# Run tests
just test

# Run tests with coverage
just test-cov

# Generate an HTML coverage report in htmlcov/
just coverage-html

# Lint, and auto-fix what can be fixed
just lint
just lint-fix

# Format, or check formatting without writing
just format
just format-check

# Type check with ty
just typecheck

# Remove build, cache, and coverage artifacts
just clean
```

### Manual Commands

If you prefer to invoke the tools directly with uv:

```bash
uv run --group dev pytest                                              # tests + coverage
uv run --group dev pytest test/ -v --cov=lib --cov-report=term-missing # detailed report
uv run --group dev pytest test/ --cov=lib --cov-report=html            # HTML report
uv run --group dev ruff check .                                        # lint
uv run --group dev ruff format .                                       # format
uv run --group dev ty check --exit-zero-on-warning lib/ test/          # type check
```

Coverage settings, including the 80% minimum, live in `pyproject.toml` and apply to
every one of these invocations.

## Versioning and Building the Gem

The plugin version is defined in one place, the `version` field of `pyproject.toml`:

```toml
[project]
name = "openc3-cosmos-script-engine-cstol-python"
version = "1.2.0"
```

The gemspec does not hardcode a version. It reads the `VERSION` environment variable,
and `just build-gem` supplies that value by reading it out of `pyproject.toml`. So
bumping the version in `pyproject.toml` is what changes the version of the built gem:

```bash
# Builds openc3-cosmos-script-engine-cstol-<pyproject version>.gem
just build-gem
```

To override the version for a one-off build, pass it explicitly:

```bash
just build-gem 1.3.0
```

For a throwaway build, `just build-gem-dev` appends a `-dev.<timestamp>` suffix to the
`pyproject.toml` version, which keeps prerelease gems from colliding. RubyGems
normalizes that into a prerelease version, so `1.2.0` builds as
`openc3-cosmos-script-engine-cstol-1.2.0.pre.dev.<timestamp>.gem`.

Both `pyproject.toml` and `uv.lock` are packaged into the gem.

## Contributing

We encourage you to contribute to OpenC3!

Contributing is easy.

1. Fork the project
2. Create a feature branch
3. Make your changes
4. Submit a pull request

YOU MUST AGREE TO THE FOLLOWING TO SUBMIT CODE TO THIS PROJECT:

FOR ALL CONTRIBUTIONS TO THE OPENC3 PROJECT, OPENC3, INC. MAINTAINS ALL RIGHTS TO ALL CODE CONTRIBUTED TO THE OPENC3 PROJECT INCLUDING THE RIGHT TO LICENSE IT UNDER OTHER TERMS.

## License

The MIT License. See [LICENSE.txt](LICENSE.txt)
