#include <iostream>
#include <string>

void logInfo(std::string message) {
    std::cout << "[INFO]  " << message << std::endl;
}

void logError(std::string message) {
    std::cout << "[ERROR] " << message << std::endl;
}

void logDebug(std::string message) {
    std::cout << "[DEBUG] " << message << std::endl;
}

void logWarning(std::string message) {
    std::cout << "[WARN]  " << message << std::endl;
}
