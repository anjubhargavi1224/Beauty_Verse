// Community.jsx
import React, { useState } from "react";
import Comm from "../assets/Comm.jpeg";
import SkincareTipsForm from "./SkincareTipsForm";

const Community = ({ onSubmitTip }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <>
      <section className="bg-gradient-to-r from-[#fff8f1] to-[#fef6f2] py-12 px-6 md:px-16 flex flex-col-reverse md:flex-row items-center justify-between gap-8 font-urbanist">
        {/* Text */}
        <div className="flex-1 text-center md:text-left">
          <h1 className="text-4xl md:text-5xl font-bold text-gray-800 leading-snug">
            Come Join Us <br />
            <span className="text-[#c0874f]">with BeautyVerse</span>
          </h1>
          <p className="mt-4 text-gray-600 text-lg max-w-md">
            Embrace skin that shines from within. Let your experience and tips guide many to the healthiest version of themselves.
          </p>
          <button
            className="mt-6 bg-[#c0874f] text-white px-6 py-3 rounded-full shadow-md hover:scale-105 transition-transform duration-300"
            onClick={() => setIsModalOpen(true)}
          >
            Share your tips and tricks
          </button>
        </div>

        {/* Image */}
        <div className="relative flex-1 flex justify-center">
          <div className="relative rounded-full overflow-hidden shadow-lg w-[300px] md:w-[360px]">
            <img src={Comm} alt="Happy glowing woman" className="w-full h-full object-cover" />
            <div className="absolute inset-0 pointer-events-none">
              <div className="absolute inset-0 before:content-[''] before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white/60 before:to-transparent before:w-full before:h-full before:transform before:rotate-12 before:animate-gloss" />
            </div>
          </div>
          <div className="absolute bottom-4 left-4 md:left-8 bg-white p-4 rounded-xl shadow-lg w-[250px]">
            <h4 className="font-semibold text-gray-800 text-sm mb-1">🌞 Morning Ritual</h4>
            <p className="text-sm text-gray-600">
              Always cleanse, moisturize, and apply SPF 30+ before stepping out.
            </p>
          </div>
          <div className="absolute top-4 right-4 md:right-8 bg-white p-4 rounded-xl shadow-lg w-[250px]">
            <h4 className="font-semibold text-gray-800 text-sm mb-1">💧 Stay Hydrated</h4>
            <p className="text-sm text-gray-600">
              Drink 2-3 liters of water daily and choose hydrating products.
            </p>
          </div>
        </div>
      </section>

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50 px-4">
          <div className="bg-white rounded-xl p-6 relative w-full max-w-xl shadow-lg">
            <button
              onClick={() => setIsModalOpen(false)}
              className="absolute top-2 right-3 text-gray-500 text-2xl hover:text-red-500 font-bold"
            >
              ×
            </button>
            <SkincareTipsForm
              onSubmitTip={(data) => {
                onSubmitTip(data);
                setIsModalOpen(false);
              }}
            />
          </div>
        </div>
      )}
    </>
  );
};

export default Community;
