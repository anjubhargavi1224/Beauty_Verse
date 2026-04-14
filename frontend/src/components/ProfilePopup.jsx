// components/ProfilePopup.jsx
import { signOut } from "firebase/auth";
import { auth } from "./Firebase";

const ProfilePopup = ({ user, onClose }) => {
  const handleLogout = () => {
    signOut(auth);
    onClose(); // Close popup after logout
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-30 z-[999]">
      <div className="bg-white p-8 rounded-lg shadow-lg w-[90%] max-w-xl relative">
        <button onClick={onClose} className="absolute top-4 right-4 text-gray-500 text-xl">✖</button>

        <div className="flex flex-col items-center text-center mb-6">
          <img
            src={user?.photoURL}
            alt="User Avatar"
            className="w-24 h-24 rounded-full object-cover border-4 border-white shadow-md"
          />
          <h2 className="mt-4 text-xl font-bold">{user?.displayName}</h2>
          <p className="text-gray-500">{user?.email}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <input className="p-2 border rounded" placeholder="Phone Number" />
          <input className="p-2 border rounded" placeholder="Location" />
          <input className="p-2 border rounded" placeholder="Full Name" />
          <input className="p-2 border rounded" placeholder="Postal Code" />
        </div>

        <button className="mt-6 w-full bg-orange-500 text-white py-2 rounded hover:bg-orange-600 transition">Save Changes</button>

        <button
          onClick={handleLogout}
          className="mt-4 w-full text-red-500 hover:underline"
        >
          Log out
        </button>
      </div>
    </div>
  );
};

export default ProfilePopup;
