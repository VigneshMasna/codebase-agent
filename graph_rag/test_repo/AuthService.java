package auth;

class AuthService extends BaseService {

    UserRepository userRepo;
    PasswordUtils passwordUtils;

    boolean login(String username, String password) {
        logInfo("Login attempt: " + username);
        if (!userRepo.exists(username)) {
            logError("User not found: " + username);
            return false;
        }
        return validateCredentials(username, password);
    }

    boolean validateCredentials(String username, String password) {
        String storedHash = userRepo.findByUsername(username);
        return passwordUtils.verifyPassword(password, storedHash);
    }

    void logout(String username) {
        logInfo("User logged out: " + username);
    }

    boolean register(String username, String password) {
        if (!passwordUtils.isStrongPassword(password)) {
            logError("Weak password for: " + username);
            return false;
        }
        String hash = passwordUtils.hashPassword(password);
        return userRepo.save(username, hash);
    }

    boolean deleteAccount(int userId, String username) {
        logInfo("Deleting account: " + username);
        return userRepo.deleteById(userId);
    }
}
