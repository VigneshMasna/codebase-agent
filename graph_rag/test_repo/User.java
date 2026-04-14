package auth;

class User {

    int id;
    String username;
    String passwordHash;
    UserRole role;
    boolean active;

    String getUsername() {
        return username;
    }

    boolean isActive() {
        return active;
    }

    boolean hasRole(UserRole requiredRole) {
        return this.role == requiredRole;
    }

    void deactivate() {
        this.active = false;
        logDeactivation(username);
    }

    void logDeactivation(String name) {
        System.out.println("User deactivated: " + name);
    }
}
