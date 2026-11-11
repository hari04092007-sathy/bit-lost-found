CREATE DATABASE IF NOT EXISTS bit_lost_found CHARACTER SET utf8mb4;
USE bit_lost_found;
CREATE TABLE users(id INT AUTO_INCREMENT PRIMARY KEY,name VARCHAR(100) NOT NULL,email VARCHAR(120) NOT NULL UNIQUE,
 department VARCHAR(100) NOT NULL,year INT NOT NULL,password_hash VARCHAR(255) NOT NULL,
 email_verified BOOLEAN NOT NULL DEFAULT FALSE,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE admins(id INT AUTO_INCREMENT PRIMARY KEY,name VARCHAR(100) NOT NULL,email VARCHAR(120) NOT NULL UNIQUE,
 password_hash VARCHAR(255) NOT NULL,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE categories(id INT AUTO_INCREMENT PRIMARY KEY,name VARCHAR(60) NOT NULL UNIQUE);
CREATE TABLE items(id INT AUTO_INCREMENT PRIMARY KEY,kind ENUM('lost','found') NOT NULL,name VARCHAR(120) NOT NULL,
 category_id INT NOT NULL,description TEXT NOT NULL,location VARCHAR(120) NOT NULL,event_date DATE NOT NULL,
 photo VARCHAR(120),contact VARCHAR(150),extra TEXT,status ENUM('pending','approved','rejected','recovered') NOT NULL DEFAULT 'pending',
 reporter_id INT NOT NULL,created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(category_id) REFERENCES categories(id),FOREIGN KEY(reporter_id) REFERENCES users(id) ON DELETE CASCADE);
CREATE TABLE claims(id INT AUTO_INCREMENT PRIMARY KEY,item_id INT NOT NULL,claimant_id INT NOT NULL,details TEXT NOT NULL,
 status ENUM('pending','approved','rejected') NOT NULL DEFAULT 'pending',created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE CASCADE,FOREIGN KEY(claimant_id) REFERENCES users(id) ON DELETE CASCADE);
INSERT IGNORE INTO categories(name) VALUES('ID Cards'),('Electronics'),('Books & Notes'),('Bags'),('Keys'),('Wallets'),('Clothing'),('Stationery'),('Other');
