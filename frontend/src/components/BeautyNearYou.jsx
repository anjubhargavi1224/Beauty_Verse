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

const darkMapStyles = [/* same dark styles */];

const BeautyNearYou = () => {
  const [userLocation, setUserLocation] = useState(null);
  const [beautyParlours, setBeautyParlours] = useState([]);
  const [activeMarker, setActiveMarker] = useState(null);

  const handleLocationSuccess = (position) => {
    const { latitude, longitude } = position.coords;
    setUserLocation({ lat: latitude, lng: longitude });
  };

  const handleLocationError = () => {
    alert('Location access is required to find nearby beauty parlours.');
  };

  const fetchNearbyBeautyParlours = useCallback(() => {
    if (!userLocation) return;

    fetch(`http://localhost:5001/api/nearby?lat=${userLocation.lat}&lng=${userLocation.lng}&type=beauty_salon&keyword=beauty%20parlour`)


      .then((res) => res.json())
      .then((data) => {
        if (data.results) {
          setBeautyParlours(data.results);
        }
      })
      .catch((error) => console.error('Failed to fetch nearby beauty parlours:', error));
  }, [userLocation]);

  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(handleLocationSuccess, handleLocationError);
    }
  }, []);

  useEffect(() => {
    if (userLocation) {
      fetchNearbyBeautyParlours();
    }
  }, [userLocation, fetchNearbyBeautyParlours]);

  const handleMarkerClick = (place) => {
    const query = encodeURIComponent(place.name + ' ' + place.vicinity);
    window.open(`https://www.google.com/maps/search/?api=1&query=${query}`, '_blank');
  };

  const handleMarkerMouseOver = (index) => setActiveMarker(index);
  const handleMarkerMouseOut = () => setActiveMarker(null);

  return (
    <div className="flex flex-col items-center w-full min-h-screen bg-gradient-to-r from-[#fff8f1] to-[#fef6f2] text-black">
      <div className="w-full text-center py-6 shadow-md bg-gradient-to-r from-[#fff8f1] to-[#fef6f2] z-10">
        <h1 className="text-3xl font-bold">Beauty Parlours Near You</h1>
      </div>

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
            {beautyParlours.map((place, idx) => (
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
                    <div style={{ animation: 'fadeInScale 0.3s ease', maxWidth: '200px', color: '#111' }}>
                      <h3 style={{ fontWeight: 'bold', fontSize: '1rem' }}>{place.name}</h3>
                      <p style={{ fontSize: '0.75rem', color: '#555' }}>{place.vicinity}</p>
                      <p style={{ fontSize: '0.75rem', color: '#333' }}>
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

export default BeautyNearYou;
