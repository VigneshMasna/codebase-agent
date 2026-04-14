package auth;

class UserRepository {

    String findByUsername(String username) {
        System.out.println("DB query: SELECT * FROM users WHERE username = " + username);
        return "hashed_password_data";
    }

    boolean save(String username, String passwordHash) {
        System.out.println("DB insert: " + username);
        return true;
    }

    boolean deleteById(int userId) {
        System.out.println("DB delete: id=" + userId);
        return true;
    }

    boolean exists(String username) {
        String result = findByUsername(username);
        return result != null;
    }
}
