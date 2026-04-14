#include <iostream>
#include <string>

// Re-declare C functions (links with math_utils.c)
extern "C" {
    int add(int a, int b);
    int subtract(int a, int b);
    int multiply(int a, int b);
    int factorial(int n);
}

class Calculator {
private:
    std::string name;
    int history;

public:
    Calculator(std::string name) : name(name), history(0) {}

    int compute(char op, int a, int b) {
        int result = 0;
        switch (op) {
            case '+': result = add(a, b); break;
            case '-': result = subtract(a, b); break;
            case '*': result = multiply(a, b); break;
            default:  result = 0;
        }
        history = result;
        return result;
    }

    int getFactorial(int n) {
        return factorial(n);
    }

    void printHistory() {
        std::cout << "[" << name << "] last result = " << history << "\n";
    }
};

int main() {
    std::cout << "=== C++ Calculator Test ===\n";
    Calculator calc("TestCalc");

    std::cout << "3 + 4 = "  << calc.compute('+', 3, 4)  << "\n";
    std::cout << "10 - 3 = " << calc.compute('-', 10, 3) << "\n";
    std::cout << "4 * 5 = "  << calc.compute('*', 4, 5)  << "\n";
    std::cout << "5! = "     << calc.getFactorial(5)      << "\n";
    calc.printHistory();

    return 0;
}
