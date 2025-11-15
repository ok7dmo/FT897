# CLAUDE.md - AI Assistant Guide for FT897 Project

## Project Overview

**FT897** is a project related to the Yaesu FT-897 amateur radio transceiver, a popular multi-band, multi-mode portable transceiver covering HF, VHF, and UHF frequencies.

### Project Status
- **Stage**: Initial/Development
- **Repository**: ok7dmo/FT897
- **Primary Branch**: main (development branches follow `claude/*` pattern)

## Repository Structure

```
FT897/
├── .git/              # Git repository metadata
├── README.md          # Project documentation
└── CLAUDE.md          # This file - AI assistant guidelines
```

### Expected Structure (as project develops)

The project may evolve to include:
- **src/** - Source code for FT897 control software/libraries
- **docs/** - Documentation, manuals, and technical references
- **examples/** - Example code and usage demonstrations
- **tests/** - Test suites and validation code
- **hardware/** - Schematics, PCB designs, or hardware interfaces
- **protocols/** - CAT (Computer Aided Transceiver) protocol documentation

## Technical Context

### FT-897 Transceiver Specifications
- **Manufacturer**: Yaesu
- **Type**: HF/VHF/UHF All-Mode Transceiver
- **Frequency Coverage**:
  - HF: 1.8-30 MHz
  - VHF: 144-146 MHz (50 MHz optional)
  - UHF: 430-450 MHz
- **Modes**: SSB, CW, AM, FM, Digital modes
- **Control**: CAT (Computer Aided Transceiver) interface via RS-232

### CAT Protocol
The FT-897 uses a proprietary CAT protocol for computer control:
- **Interface**: RS-232 serial (likely requires USB-to-serial adapter)
- **Baud Rate**: 4800, 9600, or 38400 bps
- **Data Format**: 8N2 (8 data bits, no parity, 2 stop bits)
- **Command Structure**: Binary commands (5 bytes per command)

## Development Workflows

### Branch Strategy
- **Main Branch**: `main` - stable code
- **Development Branches**: `claude/<session-id>` - AI-assisted development
- **Feature Branches**: `feature/<feature-name>` - new features
- **Bug Fixes**: `fix/<issue-description>` - bug fixes

### Git Conventions

#### Commit Messages
Follow conventional commit format:
```
type(scope): brief description

Detailed explanation (if needed)

- Additional details
- Related issues: #123
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Test additions/changes
- `chore`: Maintenance tasks

#### Push/Pull Best Practices
- Always push to feature branch first: `git push -u origin <branch-name>`
- Branch names starting with `claude/` and ending with session ID
- Retry failed network operations up to 4 times with exponential backoff (2s, 4s, 8s, 16s)

### Code Review Process
1. Create feature branch
2. Implement changes with tests
3. Run test suite
4. Create pull request with description
5. Review and merge

## AI Assistant Conventions

### Task Management
- **Always** use TodoWrite tool for multi-step tasks
- Mark todos as `in_progress` before starting work
- Mark todos as `completed` immediately after finishing
- Keep only ONE task `in_progress` at a time

### Code Quality Standards

#### Security
- Prevent command injection vulnerabilities
- Sanitize all user inputs
- Avoid XSS vulnerabilities
- Follow OWASP Top 10 guidelines
- Validate data from serial/radio interfaces

#### Testing
- Write tests for all new features
- Include unit tests for functions
- Add integration tests for CAT protocol communication
- Test error handling and edge cases

#### Documentation
- Document all public APIs
- Include docstrings for functions/classes
- Add inline comments for complex logic
- Update README.md with new features

### File Operations
- **Prefer** editing existing files over creating new ones
- **Use** Read tool before Edit or Write
- **Use** specialized tools (Read/Edit/Write) instead of bash commands
- **Avoid** creating unnecessary markdown files

### Communication Style
- Concise and technical
- No emojis unless requested
- Focus on facts over validation
- Use code references with `file:line` format
- Output directly, don't use bash echo for messages

## Common Tasks

### Radio Control Development
When developing FT-897 control features:
1. Review CAT protocol documentation
2. Implement command structure (5-byte binary format)
3. Handle serial communication properly
4. Add error handling for communication failures
5. Test with hardware or simulator
6. Document command functions

### Serial Communication
```python
# Example CAT command structure
# [P1] [P2] [P3] [P4] [CMD]
# Each command is 5 bytes total
```

Key considerations:
- Handle timeouts gracefully
- Implement retry logic for failed commands
- Validate responses from radio
- Buffer management for continuous operation

### Adding New Features
1. Check existing codebase for similar patterns
2. Use Task tool with `subagent_type=Explore` for codebase exploration
3. Create feature branch
4. Implement with tests
5. Update documentation
6. Commit and push

## Resources

### FT-897 References
- Yaesu FT-897 Operating Manual
- CAT Command Reference Manual
- Amateur Radio Bands and Regulations
- Digital Mode Protocols (PSK31, FT8, etc.)

### Development Tools
- Serial communication libraries (pyserial, node-serialport, etc.)
- Radio control software (Ham Radio Deluxe, fldigi, WSJT-X)
- Protocol analyzers for debugging

## Project-Specific Conventions

### Frequency Handling
- Store frequencies in Hz (integer)
- Display in MHz/kHz based on band
- Validate against band limits

### Mode Abbreviations
- `LSB` - Lower Sideband
- `USB` - Upper Sideband
- `CW` - Continuous Wave (Morse)
- `CWR` - CW Reverse
- `AM` - Amplitude Modulation
- `FM` - Frequency Modulation
- `DIG` - Digital modes
- `PKT` - Packet modes

### Power Levels
- QRP: ≤5W
- Low: 5-25W
- Medium: 25-50W
- High: 50-100W (FT-897D max)

## Troubleshooting

### Common Issues
1. **Serial Communication Failures**
   - Check baud rate settings
   - Verify cable connections
   - Test with known-good software

2. **Command Timeouts**
   - Increase timeout values
   - Check for correct command format
   - Verify radio is powered on

3. **Invalid Responses**
   - Validate checksum (if applicable)
   - Check for buffer overflow
   - Verify command sequence

## Version History

- **2025-11-15**: Initial CLAUDE.md created
  - Project structure documented
  - FT-897 technical context added
  - Development workflows established
  - AI assistant conventions defined

## Notes for AI Assistants

- This is an amateur radio project - follow FCC/international regulations
- CAT protocol is binary - handle byte-level operations carefully
- Serial communication requires proper error handling
- Test thoroughly before transmitting (RF safety)
- Respect frequency allocations and licensing requirements
- Consider real-time constraints for radio operation
- Document all protocol commands and responses

## Future Enhancements

As the project develops, consider adding:
- Memory channel management
- Automatic band selection
- Digital mode integration
- Logging capabilities
- Remote operation features
- Spectrum analysis tools
- Antenna tuner control
- Satellite tracking integration

---

**Last Updated**: 2025-11-15
**Maintainer**: ok7dmo
**License**: [To be determined]
