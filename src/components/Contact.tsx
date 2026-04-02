import { MdArrowOutward, MdCopyright } from "react-icons/md";
import "./styles/Contact.css";

const Contact = () => {
  return (
    <div className="contact-section section-container" id="contact">
      <div className="contact-container">
        <h3>Contact</h3>
        <div className="contact-flex">
          <div className="contact-box">
            <h4>Email</h4>
            <p>
              <a href="mailto:M.sanaullahjaved@gmail.com" data-cursor="disable">
                M.sanaullahjaved@gmail.com
              </a>
            </p>
            <h4>Phone</h4>
            <p>
              <a href="tel:+17046153787" data-cursor="disable">
                +1 704 615 3787
              </a>
            </p>
            <h4>WhatsApp</h4>
            <p>
              <a href="https://wa.me/447909231874" data-cursor="disable" target="_blank" rel="noopener noreferrer">
                +44 7909 231 874
              </a>
            </p>
            <h4>Education</h4>
            <p>BSc in Computer Science</p>
            <p>UNC Charlotte & University of Bradford</p>
          </div>
          <div className="contact-box">
            <h4>Social</h4>
            <a
              href="https://github.com/Sunny27317"
              target="_blank"
              data-cursor="disable"
              className="contact-social"
            >
              Github <MdArrowOutward />
            </a>
            <a
              href="https://www.linkedin.com/in/sana-ullah-58193b311"
              target="_blank"
              data-cursor="disable"
              className="contact-social"
            >
              Linkedin <MdArrowOutward />
            </a>
          </div>
          <div className="contact-box">
            <h2>
              Designed and Developed <br /> by <span>Sana Ullah</span>
            </h2>
            <h5>
              <MdCopyright /> 2026
            </h5>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Contact;
