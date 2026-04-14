import React from "react";

const Testimonial = ({ testimonials }) => {
  return (
    <section className="bg-gradient-to-r from-[#fff8f1] to-[#fef6f2] py-16 px-4">
      <h2 className="text-5xl font-light text-center text-[#3f3f3f] tracking-wide mb-16">
        TESTIMONIALS
      </h2>

      <div className="flex flex-col md:flex-row justify-center gap-8 max-w-6xl mx-auto">
        {testimonials.map((t, index) => (
          <div
            key={index}
            className={`relative w-full md:w-1/3 rounded-2xl shadow-xl p-6 pt-16 ${t.bgColor} text-center`}
          >
            <div className="absolute -top-12 left-1/2 transform -translate-x-1/2">
              <div className="relative w-24 h-24 rounded-full overflow-hidden border-4 border-white shadow-md mx-auto">
                <img
                  src={t.image}
                  alt={t.name}
                  className="w-full h-full object-cover"
                />
              </div>
              <p className="text-sm font-medium mt-2 text-[#333]">{t.name}</p>
            </div>
            <p className="mt-4 text-sm text-[#1f1f1f] leading-relaxed">{t.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
};

export default Testimonial;
