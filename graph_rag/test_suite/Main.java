// Java mirrors the same logic as math_utils.c and calculator.cpp
// (same function signatures, same test values — conceptually linked)

public class Main {

    static int add(int a, int b)      { return a + b; }
    static int subtract(int a, int b) { return a - b; }
    static int multiply(int a, int b) { return a * b; }

    static int factorial(int n) {
        if (n <= 1) return 1;
        return n * factorial(n - 1);
    }

    static class Calculator {
        private String name;
        private int history;

        Calculator(String name) {
            this.name = name;
            this.history = 0;
        }

        int compute(char op, int a, int b) {
            switch (op) {
                case '+': history = add(a, b);      break;
                case '-': history = subtract(a, b); break;
                case '*': history = multiply(a, b); break;
                default:  history = 0;
            }
            return history;
        }

        int getFactorial(int n) { return factorial(n); }

        void printHistory() {
            System.out.println("[" + name + "] last result = " + history);
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Java Calculator Test ===");
        Calculator calc = new Calculator("TestCalc");

        System.out.println("3 + 4 = "  + calc.compute('+', 3, 4));
        System.out.println("10 - 3 = " + calc.compute('-', 10, 3));
        System.out.println("4 * 5 = "  + calc.compute('*', 4, 5));
        System.out.println("5! = "     + calc.getFactorial(5));
        calc.printHistory();
    }
}
