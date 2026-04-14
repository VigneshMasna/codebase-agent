package auth;

class BaseService {

    String serviceName;

    void logInfo(String message) {
        System.out.println("[INFO] " + serviceName + ": " + message);
    }

    void logError(String message) {
        System.out.println("[ERROR] " + serviceName + ": " + message);
    }

    boolean isInitialized() {
        return serviceName != null && !serviceName.isEmpty();
    }
}
