import { useState, useEffect } from "react";
import { FiSearch } from "react-icons/fi";
import { IonIcon } from "@ionic/react";
import { personOutline, starOutline } from "ionicons/icons";
import { Link as RouterLink } from "react-router-dom";
import { Link as ScrollLink } from "react-scroll";
import { auth } from "../components/Firebase";
import logo from "../assets/logo.png";
import AuthPopup from "./AuthPopup";
import ProfilePopup from "./ProfilePopup"; // <-- Import new profile popup

const Navbar = () => {
  const [user, setUser] = useState(null);
  const [isFavoritesOpen, setIsFavoritesOpen] = useState(false);
  const [favorites, setFavorites] = useState([]);
  const [isAuthPopupOpen, setIsAuthPopupOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  useEffect(() => {
    const unsubscribe = auth.onAuthStateChanged((firebaseUser) => {
      setUser(firebaseUser);
    });

    const updateFavorites = () => {
      const storedFavorites = JSON.parse(localStorage.getItem("favorites")) || [];
      setFavorites(storedFavorites);
    };

    updateFavorites();
    window.addEventListener("storage", updateFavorites);

    return () => {
      unsubscribe();
      window.removeEventListener("storage", updateFavorites);
    };
  }, []);

  return (
    <>
      <nav className="w-full bg-white shadow-md z-[100]">
        <div className="container mx-auto px-4 lg:px-10 py-4 flex flex-col items-center">
          <div className="w-full flex items-center justify-between">
            {/* Search Bar */}
            <div className="flex items-center border border-gray-300 rounded-md px-3 py-2 w-1/2 md:w-1/6">
              <input
                type="text"
                placeholder="Search product"
                className="w-full focus:outline-none text-gray-500 text-sm"
              />
              <FiSearch className="text-gray-700 cursor-pointer" size={18} />
            </div>

            {/* Logo */}
            <RouterLink to="/">
              <img
                src={logo}
                alt="BeautyVerse Logo"
                className="h-14 md:h-16 w-auto object-contain"
              />
            </RouterLink>

            {/* Profile & Favorites */}
            <div className="flex space-x-6 items-center">
              {user ? (
                <img
                  src={user.photoURL}
                  alt="Profile"
                  onClick={() => setIsProfileOpen(true)}
                  className="w-8 h-8 rounded-full object-cover cursor-pointer"
                />
              ) : (
                <button onClick={() => setIsAuthPopupOpen(true)}>
                  <IonIcon icon={personOutline} size="large" className="cursor-pointer text-2xl" />
                </button>
              )}

              <button onClick={() => setIsFavoritesOpen(true)}>
                <IonIcon icon={starOutline} size="large" className="cursor-pointer text-2xl" />
              </button>
            </div>
          </div>

          {/* Navigation Links */}
          <div className="flex flex-wrap justify-center space-x-8 text-gray-700 font-semibold mt-4">
            {["home", "about", "products", "scan", "features", "FAQ", "blog", "contact-us"].map((item) => (
              <ScrollLink
                key={item}
                to={item}
                smooth={true}
                duration={500}
                className="cursor-pointer hover:text-blue-500"
              >
                {item.charAt(0).toUpperCase() + item.slice(1).replace("-", " ")}
              </ScrollLink>
            ))}
          </div>
        </div>
      </nav>

      {/* Favorites Modal */}
      {isFavoritesOpen && (
        <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-50 z-[200]">
          <div className="bg-white p-6 rounded-lg shadow-lg w-96 relative">
            <button className="absolute top-2 right-2 text-gray-500" onClick={() => setIsFavoritesOpen(false)}>✖</button>
            <h2 className="text-lg font-bold mb-4">Favorites</h2>

            {favorites.length > 0 ? (
              <ul className="list-disc list-inside space-y-2">
                {favorites.map((fav, index) => (
                  <li key={index}>{fav}</li>
                ))}
              </ul>
            ) : (
              <p className="text-gray-500">No favorites yet.</p>
            )}
          </div>
        </div>
      )}

      {/* Auth Popup */}
      {isAuthPopupOpen && (
        <AuthPopup onClose={() => setIsAuthPopupOpen(false)} setUser={setUser} />
      )}

      {/* Profile Popup */}
      {isProfileOpen && (
        <ProfilePopup user={user} onClose={() => setIsProfileOpen(false)} />
      )}
    </>
  );
};

export default Navbar;
