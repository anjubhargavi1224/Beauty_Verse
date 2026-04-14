// server.js

import express from 'express';
import cors from 'cors';

const fetch = (...args) => import('node-fetch').then(({ default: fetch }) => fetch(...args));

const app = express();
const PORT = 5001;

// Replace with your actual Google Maps API key
const GOOGLE_MAPS_API_KEY = 'AIzaSyCCldYOC83HYdgX8dGxF1Pk31wsxGKVJko';

app.use(cors());

app.get('/api/nearby', async (req, res) => {
  const { lat, lng, type, keyword } = req.query;

  if (!lat || !lng) {
    return res.status(400).json({ error: 'Latitude and longitude are required.' });
  }

  const radius = 5000;
  const placeType = type || 'doctor';
  const searchKeyword = keyword || 'dermatologist';

  const googleApiUrl = `https://maps.googleapis.com/maps/api/place/nearbysearch/json?location=${lat},${lng}&radius=${radius}&type=${placeType}&keyword=${searchKeyword}&key=${GOOGLE_MAPS_API_KEY}`;

  try {
    const response = await fetch(googleApiUrl);
    const data = await response.json();

    if (data.status !== 'OK') {
      console.error('Google API error:', data);
      return res.status(500).json({ error: 'Something went wrong with Google API' });
    }

    res.json(data);
  } catch (err) {
    console.error('Error fetching data from Google API:', err);
    res.status(500).json({ error: 'Something went wrong' });
  }
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});
