#include <iostream>
#include <string>

enum ConnectionStatus {
    CONNECTED,
    DISCONNECTED,
    CONNECTING,
    ERROR
};

struct DBConfig {
    std::string host;
    int port;
    std::string database;
};

static bool connected = false;

bool connectDB(std::string host, int port) {
    std::cout << "Connecting to " << host << ":" << port << std::endl;
    connected = true;
    return true;
}

void disconnectDB() {
    connected = false;
    std::cout << "Disconnected from DB" << std::endl;
}

bool isConnected() {
    return connected;
}

bool executeQuery(std::string query) {
    if (!isConnected()) {
        std::cout << "Error: not connected" << std::endl;
        return false;
    }
    std::cout << "Executing: " << query << std::endl;
    return true;
}
