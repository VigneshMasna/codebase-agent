#include <iostream>
#include <string>

struct User {
    int id;
    std::string username;
    std::string passwordHash;
};

bool getUser(std::string username) {
    return executeQuery("SELECT * FROM users WHERE username='" + username + "'");
}

bool createUser(std::string username, std::string passwordHash) {
    if (!isConnected()) {
        logError("Cannot create user: DB not connected");
        return false;
    }
    return executeQuery("INSERT INTO users VALUES ('" + username + "', '" + passwordHash + "')");
}

bool deleteUser(int userId) {
    if (!isConnected()) {
        logError("Cannot delete user: DB not connected");
        return false;
    }
    return executeQuery("DELETE FROM users WHERE id=" + std::to_string(userId));
}

bool updatePassword(std::string username, std::string newHash) {
    if (!getUser(username)) {
        logError("User not found: " + username);
        return false;
    }
    return executeQuery("UPDATE users SET password='" + newHash + "' WHERE username='" + username + "'");
}

void listAllUsers() {
    logInfo("Fetching all users");
    executeQuery("SELECT * FROM users");
}
