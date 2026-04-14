import { motion, AnimatePresence } from "framer-motion";
import Particles from "react-tsparticles";
import { loadFull } from "tsparticles";
import { useCallback, useEffect, useState } from "react";

export default function BeautyverseLoader() {
  const particlesInit = useCallback(async (engine) => {
    await loadFull(engine);
  }, []);

  const [showLoader, setShowLoader] = useState(true);
  const [split, setSplit] = useState(false);

  useEffect(() => {
    const timeout = setTimeout(() => setSplit(true), 3000);
    const exit = setTimeout(() => setShowLoader(false), 4500);
    return () => {
      clearTimeout(timeout);
      clearTimeout(exit);
    };
  }, []);

  return (
    <>
      <AnimatePresence>
        {showLoader && (
          <div className="fixed inset-0 z-50">
            {/* 🎆 Background Particles */}
            <Particles
              id="tsparticles"
              init={particlesInit}
              options={{
                background: { color: { value: "#fdf2f8" } },
                particles: {
                  number: { value: 20 },
                  size: { value: 2 },
                  move: { enable: true, speed: 0.6 },
                  opacity: { value: 0.2 },
                  color: { value: "#f472b6" },
                  links: { enable: false },
                },
                interactivity: { events: { resize: true } },
                fpsLimit: 60,
              }}
              className="absolute inset-0 z-0"
            />

            {/* 💎 Loader Content - Centered */}
            {!split && (
              <motion.div
                className="absolute inset-0 z-40 flex items-center justify-center"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 1 }}
              >
                <motion.div
                  className="flex flex-col items-center justify-center text-center"
                  initial={{ scale: 0.9 }}
                  animate={{ scale: 1 }}
                  transition={{ duration: 1 }}
                >
                  <motion.div
                    className="w-20 h-20 border-4 border-pink-300 border-t-fuchsia-500 rounded-full animate-spin"
                    style={{ borderTopColor: "#d946ef" }}
                  ></motion.div>
                  <motion.h2
                    className="mt-6 text-lg font-semibold text-gray-700 font-[Poppins]"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 }}
                  >
                    Beautyverse is preparing your experience...
                  </motion.h2>
                </motion.div>
              </motion.div>
            )}

            {/* 🔼 Top Half */}
            <motion.div
              initial={{ y: 0 }}
              animate={{ y: split ? "-100%" : 0 }}
              exit={{ y: "-100%" }}
              transition={{ duration: 1.5, ease: "easeInOut" }}
              className="absolute top-0 left-0 w-full h-1/2 bg-[#f8f6c4] z-30"
            ></motion.div>

            {/* 🔽 Bottom Half */}
            <motion.div
              initial={{ y: 0 }}
              animate={{ y: split ? "100%" : 0 }}
              exit={{ y: "100%" }}
              transition={{ duration: 1.5, ease: "easeInOut" }}
              className="absolute bottom-0 left-0 w-full h-1/2 bg-[#f8f6c4] z-30"
            ></motion.div>
          </div>
        )}
      </AnimatePresence>

     
    </>
  );
}
