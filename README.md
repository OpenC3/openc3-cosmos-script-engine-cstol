## OpenC3 Load Sim Plugin

[Documentation](http://openc3.com)

This plugin provides a CSTOL script engine that allows COSMOS ScriptRunner to execute CSTOL scripts.

The following CSTOL keywords are supported:

- ASK
- BEGIN
- CHECK
- CLEAR
- DECLARE
- DISPLAY
- ELSE
- ELSEIF
- END
- ENDIF
- ENDLOOP
- ENDMACRO
- ENDPROC
- ESCAPE
- GOTO
- IF
- LET
- LOOP
- PROC
- RUN
- START
- SWITCH
- WAIT
- WRITE

The following CSTOL command keywards are supported:

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

The following keywords behave differently:

- LOAD - takes an interface name instead of a target name to load data to
- SEND - takes an interface name instead of a target name to send data to

The following CSTOL keywords are not supported and will simply print a warning:

- CANCEL
- CHECKPOINT
- COMMIT
- COMPILE
- CSTOL
- DECOMPILE
- DEFINE
- DELETE
- FLUSH
- INSERT
- LOCK
- MACRO
- RECORD
- REPORT
- RESTORE
- RETREIVE
- RETRY
- SHOW
- SNAP
- STOP
- UNDEFINE
- UNLOCK
- UPDATE
- ROUTE

## Getting Started

1.  At the Administrator Console - Plugins, upload the openc3-cosmos-script-engine-cstol.gem file

## Testing

### Run tests with coverage

source test_env/bin/activate
python -m pytest

### Generate detailed terminal report

python -m pytest --cov=lib --cov-report=term-missing

### Generate HTML report

python -m pytest --cov=lib --cov-report=html

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

OpenC3 is released under the AGPL v3 with a few addendums. See [LICENSE.txt](LICENSE.txt)
