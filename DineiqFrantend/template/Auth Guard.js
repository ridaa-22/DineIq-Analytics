// auth-guard.js
(function() {
  const token = localStorage.getItem('authToken');

  // Agar token nahi mila toh seedha login.html par bhej do
  if (!token) {
    alert('Access Denied! Pehle login karein.');
    window.location.href = 'login.html';
  }
})();