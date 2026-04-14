# Test Suite

Simple interlinked C / C++ / Java test suite.

## Structure

| File            | Role                                      |
|-----------------|-------------------------------------------|
| math_utils.h    | C header — shared function declarations   |
| math_utils.c    | C implementation of add/subtract/multiply/factorial |
| calculator.cpp  | C++ class that calls the C functions via `extern "C"` |
| Main.java       | Java mirror — same functions, same test values |

## Build & Run

### C
```bash
gcc math_utils.c -o math_utils && ./math_utils
```

### C++ (links with C object)
```bash
gcc -c math_utils.c -o math_utils.o
g++ calculator.cpp math_utils.o -o calculator && ./calculator
```

### Java
```bash
javac Main.java && java Main
```
