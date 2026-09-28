const express = require('express');
const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const cors = require('cors');

const app = express();
app.use(express.json());
app.use(cors());

// 1. MongoDB Connection (Local 'dineiq' Database)
mongoose.connect('mongodb://127.0.0.1:27017/dineiq')
  .then(() => console.log('MongoDB Connected Successfully to dineiq DB'))
  .catch(err => console.error('MongoDB Connection Error:', err));

// 2. User Schema & Model
const userSchema = new mongoose.Schema({
  username: { type: String, required: true },
  email: { type: String, required: true, unique: true },
  password: { type: String, required: true },
  createdAt: { type: Date, default: Date.now }
});

const User = mongoose.model('User', userSchema);

const JWT_SECRET = 'your_super_secret_key_123';

// 3. REGISTER API (Saves user data in MongoDB)
app.post('/api/register', async (req, res) => {
  try {
    const { username, email, password } = req.body;

    // Check if user already exists
    const existingUser = await User.findOne({ email });
    if (existingUser) {
      return res.status(400).json({ success: false, message: 'Email pehle se registered hai!' });
    }

    // Encrypt Password
    const hashedPassword = await bcrypt.hash(password, 10);

    // Save New User
    const newUser = new User({
      username,
      email,
      password: hashedPassword
    });

    await newUser.save();
    res.status(201).json({ success: true, message: 'Account successfully create ho gaya!' });

  } catch (error) {
    res.status(500).json({ success: false, message: 'Server error: ' + error.message });
  }
});

// 4. LOGIN API (Authenticates User)
app.post('/api/login', async (req, res) => {
  try {
    const { email, password } = req.body;

    const user = await User.findOne({ email });
    if (!user) {
      return res.status(400).json({ success: false, message: 'Email galat hai ya account nahi mila!' });
    }

    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) {
      return res.status(400).json({ success: false, message: 'Galat Password! Dubara koshish karein.' });
    }

    const token = jwt.sign({ id: user._id, email: user.email }, JWT_SECRET, { expiresIn: '1h' });

    res.status(200).json({
      success: true,
      message: 'Login Successful',
      token,
      user: { username: user.username, email: user.email }
    });

  } catch (error) {
    res.status(500).json({ success: false, message: 'Server error: ' + error.message });
  }
});

// 5. GET ALL USERS & TOTAL COUNT API (Total kitne registered users hain dekhne ke liye)
app.get('/api/users', async (req, res) => {
  try {
    const users = await User.find({}, '-password'); // Password hidden rahega security ke liye
    const totalUsers = await User.countDocuments(); // Count calculate karega
    
    res.status(200).json({
      success: true,
      totalUsersCount: totalUsers,
      usersList: users
    });
  } catch (error) {
    res.status(500).json({ success: false, message: 'Server error: ' + error.message });
  }
});

// Server Start
app.listen(5000, () => console.log('Server running on http://localhost:5000'));