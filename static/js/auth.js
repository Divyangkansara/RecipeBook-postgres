// static/js/auth.js

// Registration
document.getElementById('registerForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    const response = await fetch('/auth/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password, is_email_verified: false, roles: ['User'] }),
    });

    const data = await response.json();

    if (response.ok) {
        document.getElementById('message').innerText = 'Registration successful. Please check your email to verify your account.';
    } else {
        document.getElementById('message').innerText = data.detail;
    }
});

// Login
document.getElementById('loginForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    const response = await fetch('/auth/token', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `username=${username}&password=${password}`,
    });

    const data = await response.json();

    if (response.ok) {
        localStorage.setItem('token', data.access_token);
        console.log(data.access_token)
        console.log("Token stored in local storage")
        window.location.href = '/';
        document.getElementById('message').innerText = 'Login successful!';
        console.log("Login successfully")
    } else {
        document.getElementById('message').innerText = data.detail;
    }
});


//  web socket

const ws = new WebSocket("ws://localhost:8000/ws/ratings/");

ws.onopen = () => {
    console.log("Connected to WebSocket");
};

ws.onmessage = (event) => {
    const data = event.data;
    console.log("New message from server:", data);
    // Update the UI with the new rating information
};

ws.onclose = () => {
    console.log("Disconnected from WebSocket");
};

// To send a message to the server
ws.send("Hello, server!");


