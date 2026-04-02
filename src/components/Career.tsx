import "./styles/Career.css";

const Career = () => {
  return (
    <div className="career-section section-container">
      <div className="career-container">
        <h2>
          My career <span>&</span>
          <br /> experience
        </h2>
        <div className="career-info">
          <div className="career-timeline">
            <div className="career-dot"></div>
          </div>
          <div className="career-info-box">
            <div className="career-info-in">
              <div className="career-role">
                <h4>BS Computer Science</h4>
                <h5>University of Bradford, UK</h5>
              </div>
              <h3>2023</h3>
            </div>
            <p>
              Began undergraduate studies in Computer Science. Received the
              High Achiever Award in first year for academic excellence in
              Engineering and Digital Technologies.
            </p>
          </div>
          <div className="career-info-box" style={{ marginTop: "-20px" }}>
            <div className="career-info-in">
              <div className="career-role" style={{ borderLeft: "2px solid var(--accentColor)", paddingLeft: "15px" }}>
                <h4>BS Computer Science (Cont.)</h4>
                <h5>UNC Charlotte, NC</h5>
              </div>
              <h3>2025</h3>
            </div>
            <p>
              In 2025, I transferred to the University of North Carolina at Charlotte (UNC Charlotte) as part of an academic exchange program, where I am continuing my BS in Computer Science and achieved a GPA of 3.75.
            </p>
          </div>
          <div className="career-info-box">
            <div className="career-info-in">
              <div className="career-role">
                <h4>Web Developer</h4>
                <h5>AMC Food Warehouse – Bradford, UK</h5>
              </div>
              <h3>2025</h3>
            </div>
            <p>
              Developed and maintained internal and public-facing web pages.
              Improved usability, performance, and mobile responsiveness.
              Collaborated with non-technical staff to translate operational
              needs into functional IT solutions.
            </p>
          </div>
          <div className="career-info-box">
            <div className="career-info-in">
              <div className="career-role">
                <h4>Software Engineering Intern</h4>
                <h5>Summit Street – Charlotte, NC</h5>
              </div>
              <h3>NOW</h3>
            </div>
            <p>
              Building backend tools and automating data workflows with Python
              and APIs. Validating data outputs, troubleshooting issues, and
              contributing to internal dashboards in agile sprints while
              simultaneously pursuing a BS in CS at UNC Charlotte (GPA: 3.75).
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Career;
