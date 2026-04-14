package auth;

class PasswordUtils {

    String hashPassword(String password) {
        String salt = generateSalt();
        return Integer.toHexString((password + salt).hashCode());
    }

    boolean verifyPassword(String password, String storedHash) {
        String computed = hashPassword(password);
        return computed.equals(storedHash);
    }

    String generateSalt() {
        return Long.toHexString(System.currentTimeMillis());
    }

    boolean isStrongPassword(String password) {
        if (password == null || password.length() < 8) {
            return false;
        }
        boolean hasUpper = false;
        boolean hasDigit = false;
        for (char c : password.toCharArray()) {
            if (Character.isUpperCase(c)) hasUpper = true;
            if (Character.isDigit(c)) hasDigit = true;
        }
        return hasUpper && hasDigit;
    }
}
