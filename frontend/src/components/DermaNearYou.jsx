import React, { useEffect, useState, useCallback } from 'react';
import { GoogleMap, LoadScript, Marker, InfoWindow } from '@react-google-maps/api';

const GOOGLE_MAPS_API_KEY = 'AIzaSyCCldYOC83HYdgX8dGxF1Pk31wsxGKVJko';
const libraries = ['places'];

const mapContainerStyle = {
  width: '100%',
  height: '100%',
};

const centerDefault = {
  lat: 12.9716,
  lng: 77.5946,
};

const darkMapStyles = [
  { elementType: 'geometry', stylers: [{ color: '#1d1d1d' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#8a8a8a' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#1d1d1d' }] },
  {
    featureType: 'poi',
    elementType: 'geometry',
    stylers: [{ color: '#2a2a2a' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry',
    stylers: [{ color: '#333333' }],
  },
  {
    featureType: 'water',
    elementType: 'geometry',
    stylers: [{ color: '#000000' }],
  },
];

const DermaNearYou = () => {
  const [userLocation, setUserLocation] = useState(null);
  const [dermatologists, setDermatologists] = useState([]);
  const [activeMarker, setActiveMarker] = useState(null);

  const handleLocationSuccess = (position) => {
    const { latitude, longitude } = position.coords;
    setUserLocation({ lat: latitude, lng: longitude });
  };

  const handleLocationError = () => {
    alert('Location access is required to find nearby dermatologists.');
  };

  const fetchNearbyDermatologists = useCallback(() => {
    if (!userLocation) return;

    fetch(`http://localhost:5001/api/nearby?lat=${userLocation.lat}&lng=${userLocation.lng}`)
      .then((res) => res.json())
      .then((data) => {
        if (data.results) {
          setDermatologists(data.results);
        }
      })
      .catch((error) => console.error('Failed to fetch nearby places:', error));
  }, [userLocation]);

  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(handleLocationSuccess, handleLocationError);
    }
  }, []);

  useEffect(() => {
    if (userLocation) {
      fetchNearbyDermatologists();
    }
  }, [userLocation, fetchNearbyDermatologists]);

  const handleMarkerClick = (place) => {
    const query = encodeURIComponent(place.name + ' ' + place.vicinity);
    window.open(`https://www.google.com/maps/search/?api=1&query=${query}`, '_blank');
  };

  const handleMarkerMouseOver = (index) => setActiveMarker(index);
  const handleMarkerMouseOut = () => setActiveMarker(null);

  return (
    <div className="flex flex-col items-center w-full min-h-screen bg-gradient-to-r from-[#fff8f1] to-[#fef6f2] text-black">
      {/* Header Section */}
      <div className="w-full text-center py-6 shadow-md bg-gradient-to-r from-[#fff8f1] to-[#fef6f2] z-10">
        <h1 className="text-3xl font-bold">Dermatologists Near You</h1>
      </div>

      {/* Map Section */}
      <div className="w-[90%] max-w-5xl h-[80vh] mt-4 rounded-xl overflow-hidden shadow-lg">
        <LoadScript googleMapsApiKey={GOOGLE_MAPS_API_KEY} libraries={libraries}>
          <GoogleMap
            mapContainerStyle={mapContainerStyle}
            center={userLocation || centerDefault}
            zoom={14}
            options={{
              styles: darkMapStyles,
              disableDefaultUI: true,
            }}
          >
            {dermatologists.map((place, idx) => (
              <Marker
                key={idx}
                position={{
                  lat: place.geometry.location.lat,
                  lng: place.geometry.location.lng,
                }}
                onMouseOver={() => handleMarkerMouseOver(idx)}
                onMouseOut={handleMarkerMouseOut}
                onClick={() => handleMarkerClick(place)}
              >
                {activeMarker === idx && (
                  <InfoWindow
                    position={{
                      lat: place.geometry.location.lat,
                      lng: place.geometry.location.lng,
                    }}
                    options={{
                      pixelOffset: new window.google.maps.Size(0, -40),
                    }}
                  >
                    <div
                      style={{
                        animation: 'fadeInScale 0.3s ease',
                        maxWidth: '200px',
                        color: '#111',
                        fontFamily: 'Arial, sans-serif',
                      }}
                    >
                      <h3 style={{ fontWeight: 'bold', fontSize: '1rem', marginBottom: '0.25rem' }}>
                        {place.name}
                      </h3>
                      <p style={{ fontSize: '0.75rem', color: '#555' }}>{place.vicinity}</p>
                      <p style={{ fontSize: '0.75rem', color: '#333', marginTop: '0.25rem' }}>
                        ⭐ {place.rating || 'N/A'} ({place.user_ratings_total || 0} reviews)
                      </p>
                    </div>
                  </InfoWindow>
                )}
              </Marker>
            ))}
          </GoogleMap>
        </LoadScript>
      </div>

      {/* CSS Animation */}
      <style>
        {`
          @keyframes fadeInScale {
            0% {
              opacity: 0;
              transform: scale(0.8);
            }
            100% {
              opacity: 1;
              transform: scale(1);
            }
          }
        `}
      </style>
    </div>
  );
};

export default DermaNearYou;
