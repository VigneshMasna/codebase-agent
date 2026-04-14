package auth;

enum UserRole {
    ADMIN,
    USER,
    GUEST,
    MODERATOR;

    boolean isAdmin() {
        return this == ADMIN;
    }

    boolean canModerate() {
        return this == ADMIN || this == MODERATOR;
    }

    boolean isGuest() {
        return this == GUEST;
    }
}
