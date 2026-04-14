package auth;

class SessionManager extends BaseService {

    AuthService authService;
    UserRepository userRepo;
    int maxSessions;

    boolean createSession(String username, String password) {
        logInfo("Creating session for: " + username);
        if (!validateUser(username)) {
            logError("Unknown user, session denied: " + username);
            return false;
        }
        if (!authService.login(username, password)) {
            logError("Auth failed for: " + username);
            return false;
        }
        return allocateSession(username);
    }

    boolean validateUser(String username) {
        return userRepo.exists(username);
    }

    boolean allocateSession(String username) {
        logInfo("Allocating session slot for: " + username);
        return isInitialized();
    }

    void destroySession(String username) {
        logInfo("Destroying session: " + username);
        authService.logout(username);
    }

    boolean renewSession(String username, String password) {
        destroySession(username);
        return createSession(username, password);
    }

    int getMaxSessions() {
        return maxSessions;
    }
}
