import React, { useEffect, useState } from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import { onAuthStateChanged } from "firebase/auth";
import { auth } from "./components/Firebase";

import Home from "./pages/Home/Homes";
import Makeupblog from "./pages/Blog/Makeupblog";
import Dermatologyblog from "./pages/Blog/Dermatologyblog";
import Skincareblog from "./pages/Blog/Skincareblog";
import Questionnaire from "./pages/Questionnaire/Questionnaire";

import Navbar from "./components/Navbar";
import Header from "./components/Header";
import AuthPopup from "./components/AuthPopup";
import ProfilePopup from "./components/ProfilePopup";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

function App() {
  const [user, setUser] = useState(null);
  const [isAuthPopupOpen, setIsAuthPopupOpen] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
    });
    return () => unsubscribe();
  }, []);

  return (
    <Router>
      <Header />
      <Navbar user={user} setIsAuthPopupOpen={setIsAuthPopupOpen} />
      {isAuthPopupOpen && <AuthPopup setIsAuthPopupOpen={setIsAuthPopupOpen} />}

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/skincare" element={<Skincareblog />} />
        <Route path="/makeup" element={<Makeupblog />} />
        <Route path="/dermatologist" element={<Dermatologyblog />} />
        <Route path="/questionnaire" element={<Questionnaire />} />
      </Routes>

      <ToastContainer />
    </Router>
  );
}

export default App;
