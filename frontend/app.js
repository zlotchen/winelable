const submissionsList = document.getElementById("submissions-list");
const reviewPanel = document.getElementById("review-panel");
const labelImages = document.getElementById("label-images");
const applicationMeta = document.getElementById("application-meta");
const runReviewBtn = document.getElementById("run-review-btn");
const reviewResult = document.getElementById("review-result");

let currentSubmission = null;

// Load submissions on page start
async function loadSubmissions() {
  try {
    const res = await fetch("/api/submissions");
    const submissions = await res.json();
    renderSubmissions(submissions);
  } catch (err) {
    submissionsList.textContent = "Failed to load submissions.";
    console.error(err);
  }
}

function renderSubmissions(submissions) {
  if (!submissions.length) {
    submissionsList.textContent = "No pending submissions.";
    return;
  }
  submissionsList.innerHTML = "";
  submissions.forEach((s) => {
    const card = document.createElement("div");
    card.className = `submission-card status-${s.status}`;
    card.innerHTML = `
      <div class="vendor">Vendor: ${s.vendor_code}</div>
      <div class="ttb-id">TTB ID: ${s.TTB_ID}</div>
      <div class="ttb-id">Submitted: ${s.date_submission}</div>
      <span class="status">${s.status}</span>
    `;
    card.addEventListener("click", () => selectSubmission(s));
    submissionsList.appendChild(card);
  });
}

function selectSubmission(submission) {
  currentSubmission = submission;
  reviewPanel.classList.remove("hidden");
  reviewResult.classList.add("hidden");
  reviewResult.textContent = "";

  // Show images
  labelImages.innerHTML = "";
  (submission.images || []).forEach(({ image }) => {
    const img = document.createElement("img");
    img.src = `/data/${image.location.replace(/^data\//, "")}`;
    img.alt = image.file_name;
    img.title = image.file_name;
    labelImages.appendChild(img);
  });

  // Show metadata
  applicationMeta.innerHTML = `
    <strong>Application:</strong> ${submission.application}<br>
    <strong>Vendor Code:</strong> ${submission.vendor_code}<br>
    <strong>TTB ID:</strong> ${submission.TTB_ID}<br>
    <strong>Date Submitted:</strong> ${submission.date_submission}<br>
    <strong>Status:</strong> ${submission.status}
  `;
}

runReviewBtn.addEventListener("click", async () => {
  if (!currentSubmission) return;
  runReviewBtn.disabled = true;
  runReviewBtn.textContent = "Running…";
  reviewResult.classList.remove("hidden");
  reviewResult.textContent = "Waiting for model response…";

  try {
    const res = await fetch("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ TTB_ID: currentSubmission.TTB_ID, images: currentSubmission.images }),
    });
    const data = await res.json();
    reviewResult.textContent = data.result || JSON.stringify(data, null, 2);
  } catch (err) {
    reviewResult.textContent = "Error contacting server: " + err.message;
  } finally {
    runReviewBtn.disabled = false;
    runReviewBtn.textContent = "Run AI Review";
  }
});

loadSubmissions();
