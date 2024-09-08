// Ambil nama perusahaan dari elemen HTML
const companyName = document.getElementById('company-name').value; // Misalnya nama diambil dari elemen HTML

// Function to fetch geolocation data from backend
async function fetchGeolocation(companyName) {
    try {
        // Ubah URL fetch untuk menyertakan nama perusahaan
        const response = await fetch(`/geolocation?name=${encodeURIComponent(companyName)}`);
        const data = await response.json();

        if (data.latitude && data.longitude) {
            // Initialize map with the fetched coordinates
            var map = L.map('map').setView([data.latitude, data.longitude], 13);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors'
            }).addTo(map);

            // Add marker
            L.marker([data.latitude, data.longitude]).addTo(map)
                .bindPopup(data.address)
                .openPopup();
        } else {
            console.error('Invalid geolocation data');
        }
    } catch (error) {
        console.error('Error fetching geolocation:', error);
    }
}

// Call the function to fetch and display geolocation
fetchGeolocation(companyName);
