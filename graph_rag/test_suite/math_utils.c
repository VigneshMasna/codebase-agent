#include <stdio.h>
#include "math_utils.h"

int add(int a, int b) {
    return a + b;
}

int subtract(int a, int b) {
    return a - b;
}

int multiply(int a, int b) {
    return a * b;
}

int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

// Simple test runner
int main() {
    printf("=== C Math Utils Test ===\n");
    printf("add(3, 4)       = %d\n", add(3, 4));
    printf("subtract(10, 3) = %d\n", subtract(10, 3));
    printf("multiply(4, 5)  = %d\n", multiply(4, 5));
    printf("factorial(5)    = %d\n", factorial(5));
    return 0;
}
