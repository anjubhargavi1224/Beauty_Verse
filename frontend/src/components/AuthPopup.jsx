import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { signInWithPopup } from "firebase/auth";
import { auth, googleProvider } from "./Firebase";
import { PersonOutline } from "@mui/icons-material";

const AuthPopup = ({ onClose, setUser }) => {
  const [isSignUp, setIsSignUp] = useState(false);

  const handleGoogleSignIn = async () => {
    try {
      const result = await signInWithPopup(auth, googleProvider);
      const user = result.user;
      console.log("Signed in as:", user.displayName);
      setUser(user); // Send user to parent (Navbar)
      onClose(); // Close popup
    } catch (error) {
      console.error("Error signing in with Google:", error.message);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
      <AnimatePresence mode="wait">
        <motion.div
          key={isSignUp ? "signup" : "login"}
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="bg-[#FFDBBB] text-center w-[420px] p-6 rounded-xl shadow-xl relative"
        >
          <button
            onClick={onClose}
            className="absolute top-2 right-2 text-xl text-gray-600"
          >
            &times;
          </button>

          <h2 className="text-2xl font-bold mb-1">Welcome to</h2>
          <h1 className="text-3xl font-extrabold text-black mb-2">BeautyVerse</h1>
          <p className="text-sm text-gray-600 mb-5">
            Discover your true radiance with BeautyVerse. <br />
            Slay naturally with skincare tailored just for you.
          </p>

          {isSignUp ? (
            <form className="flex flex-col gap-3 text-left text-sm mb-3">
              <input type="text" placeholder="Full name" className="p-2 rounded border border-gray-300" />
              <input type="email" placeholder="Email address" className="p-2 rounded border border-gray-300" />
              <input type="password" placeholder="Password" className="p-2 rounded border border-gray-300" />
              <input type="password" placeholder="Confirm password" className="p-2 rounded border border-gray-300" />
              <p className="text-xs text-gray-500 mt-[-8px] mb-1">
                The password must contain at least 8 characters, including upper and lower case letters and numbers.
              </p>
              <label className="flex items-center gap-2">
                <input type="checkbox" />
                <span className="text-xs">Remember me</span>
              </label>
              <button className="bg-black text-white py-2 rounded">Sign Up</button>
            </form>
          ) : (
            <>
              <form className="flex flex-col gap-3 text-left mb-4">
                <input type="email" placeholder="Enter email" className="p-2 rounded border border-gray-300" />
                <input type="password" placeholder="Enter password" className="p-2 rounded border border-gray-300" />
                <button className="bg-black text-white py-2 rounded">Log In</button>
              </form>

              <button
                className="border border-black text-black py-2 rounded w-full"
                onClick={() => setIsSignUp(true)}
              >
                Sign Up
              </button>

              <p className="text-sm mt-3 text-gray-600">Continue without registration</p>

              <div className="text-sm mt-4 text-gray-600">--Or continue with--</div>
              <div className="flex justify-center my-2">
                <button onClick={handleGoogleSignIn}>
                  <img
                    src="https://developers.google.com/identity/images/btn_google_signin_dark_normal_web.png"
                    alt="Google Sign-In"
                    className="h-10"
                  />
                </button>
              </div>
            </>
          )}

          {isSignUp && (
            <p className="text-sm mt-2">
              Already have an account?{" "}
              <button onClick={() => setIsSignUp(false)} className="text-black underline">
                Log in
              </button>
            </p>
          )}

          <p className="text-xs text-gray-500 mt-4">
            By continuing you accept our{" "}
            <a href="#" className="underline text-black">Privacy Policy</a> and{" "}
            <a href="#" className="underline text-black">Terms of Service</a>
          </p>
        </motion.div>
      </AnimatePresence>
    </div>
  );
};

export default AuthPopup;
