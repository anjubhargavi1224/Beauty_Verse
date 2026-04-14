import React, { useState } from "react";
import Community from "./Community";
import Testimonial from "./Testimonial";
import user1 from "../assets/user1.jpeg";
import user2 from "../assets/user2.jpeg";
import user3 from "../assets/user3.jpeg";

const userImages = [user1, user2, user3];

const MainCommunityPage = () => {
  const [testimonials, setTestimonials] = useState([
    {
      name: "Alice",
      text: "Drinking more water and using aloe vera at night helped my acne.",
      image: user1,
      bgColor: "bg-[#ffe0b2]",
    },
    {
      name: "Raj",
      text: "I use green tea toner every morning. Works like magic!",
      image: user2,
      bgColor: "bg-[#dcedc8]",
    },
  ]);

  const addTestimonial = ({ name, tip }) => {
    const randomImage = userImages[Math.floor(Math.random() * userImages.length)];
    
    const newTestimonial = {
      name,
      text: tip,
      image: randomImage,
      bgColor: "bg-[#f0f4c3]",
    };

    setTestimonials((prev) => [newTestimonial, ...prev]);
  };

  return (
    <>
      <Community onSubmitTip={addTestimonial} />
      <Testimonial testimonials={testimonials} />
    </>
  );
};

export default MainCommunityPage;
