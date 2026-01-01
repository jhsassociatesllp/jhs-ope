let formCounter = 1;
let allHistoryData = [];
let originalRowData = {};
let savedEntries = []; // Temporary storage for saved entries
// API_URL = "http://127.0.0.1:8000";
API_URL = "";


// Add CSS animations for popups
const style = document.createElement('style');
style.textContent = `
  @keyframes slideUp {
    from {
      transform: translateY(30px);
      opacity: 0;
    }
    to {
      transform: translateY(0);
      opacity: 1;
    }
  }
  
  @keyframes scaleIn {
    from {
      transform: scale(0);
    }
    to {
      transform: scale(1);
    }
  }
  
  @keyframes progressBar {
    from {
      transform: translateX(-100%);
    }
    to {
      transform: translateX(0);
    }
  }
`;
document.head.appendChild(style);

// Month range configuration with date ranges
const monthRanges = {
  'sep-oct-2025': { start: '2025-09-21', end: '2025-10-20', display: 'Sep 2025 - Oct 2025' },
  'oct-nov-2025': { start: '2025-10-21', end: '2025-11-20', display: 'Oct 2025 - Nov 2025' },
  'nov-dec-2025': { start: '2025-11-21', end: '2025-12-20', display: 'Nov 2025 - Dec 2025' }
};

// Validate if date is within selected month range
function isDateInMonthRange(dateStr, monthRangeKey) {
  if (!monthRangeKey || !monthRanges[monthRangeKey]) {
    return false;
  }
  
  const range = monthRanges[monthRangeKey];
  const selectedDate = new Date(dateStr);
  const startDate = new Date(range.start);
  const endDate = new Date(range.end);
  
  return selectedDate >= startDate && selectedDate <= endDate;
}

// Get next date for new row
function getNextDate(currentDate) {
  const date = new Date(currentDate);
  date.setDate(date.getDate() + 1);
  return date.toISOString().split('T')[0];
}

// Get start date for selected month range
function getStartDateForMonth(monthRangeKey) {
  if (monthRanges[monthRangeKey]) {
    return monthRanges[monthRangeKey].start;
  }
  return today;
}

// toggle Button
function toggleMenu() {
  const navbar = document.getElementById('navbar');
  navbar.classList.toggle('active');
}

// Set today's date as default
const today = new Date().toISOString().split('T')[0];

// Close menu when clicking outside
document.addEventListener('click', function(event) {
  const navbar = document.getElementById('navbar');
  const menuToggle = document.querySelector('.menu-toggle');
  
  if (navbar && menuToggle && !navbar.contains(event.target) && !menuToggle.contains(event.target)) {
    navbar.classList.remove('active');
  }
});

// Success Popup Function
// Success Popup Function - UPDATED
function showSuccessPopup(message) {
  const overlay = document.createElement('div');
  overlay.style.cssText = `
    position: fixed;
    inset: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.6);
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  `;

  const popup = document.createElement('div');
  popup.style.cssText = `
    background: white;
    padding: 30px 25px;
    border-radius: 16px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    text-align: center;
    max-width: 450px;
    width: 90%;
    animation: slideUp 0.3s ease;
  `;

  // ✅ UPDATED: Removed progress bar, centered text
  popup.innerHTML = `
    <div style="
      width: 70px;
      height: 70px;
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 18px;
      animation: scaleIn 0.4s ease;
    ">
      <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
        <polyline points="20 6 9 17 4 12"></polyline>
      </svg>
    </div>
    <h2 style="font-size: 21px; color: #1f2937; margin-bottom: 10px; font-weight: 600;">Success!</h2>
    <p style="color: #6b7280; margin-bottom: 0; font-size: 14.5px; line-height: 1.5; word-wrap: break-word; text-align: center;">${message}</p>
  `;

  overlay.appendChild(popup);
  document.body.appendChild(overlay);

  // Button hover effect
  const okBtn = document.getElementById('okBtn');
  okBtn.addEventListener('mouseenter', () => {
    okBtn.style.transform = 'translateY(-2px)';
    okBtn.style.boxShadow = '0 6px 16px rgba(16, 185, 129, 0.4)';
  });
  okBtn.addEventListener('mouseleave', () => {
    okBtn.style.transform = 'translateY(0)';
    okBtn.style.boxShadow = '0 4px 12px rgba(16, 185, 129, 0.3)';
  });

  okBtn.addEventListener('click', function() {
    document.body.removeChild(overlay);
  });

  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) {
      document.body.removeChild(overlay);
    }
  });
}

// Error Popup Function
// Error Popup Function - UPDATED
function showErrorPopup(message) {
  const overlay = document.createElement('div');
  overlay.style.cssText = `
    position: fixed;
    inset: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.6);
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
  `;

  const popup = document.createElement('div');
  popup.style.cssText = `
    background: white;
    padding: 30px 25px;
    border-radius: 16px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    text-align: center;
    max-width: 450px;
    width: 90%;
    animation: slideUp 0.3s ease;
    max-height: 80vh;
    overflow-y: auto;
  `;

  popup.innerHTML = `
    <div style="
       width: 70px;
      height: 70px;
      background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 18px;
      animation: scaleIn 0.4s ease;
    ">
      <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    </div>
    <h2 style="font-size: 21px; color: #1f2937; margin-bottom: 10px; font-weight: 600;">Error</h2>
    <div style="
      color: #6b7280;
      margin-bottom: 0;
      font-size: 14px;
      line-height: 1.6;
      text-align: center;
      max-height: 250px;
      overflow-y: auto;
      word-wrap: break-word;
      padding: 0 10px;
    ">${message}</div>
  `;


  overlay.appendChild(popup);
  document.body.appendChild(overlay);

  // Button hover effect
  const okBtn = document.getElementById('okBtn');
  okBtn.addEventListener('mouseenter', () => {
    okBtn.style.transform = 'translateY(-2px)';
    okBtn.style.boxShadow = '0 6px 16px rgba(239, 68, 68, 0.4)';
  });
  okBtn.addEventListener('mouseleave', () => {
    okBtn.style.transform = 'translateY(0)';
    okBtn.style.boxShadow = '0 4px 12px rgba(239, 68, 68, 0.3)';
  });

  okBtn.addEventListener('click', function() {
    document.body.removeChild(overlay);
  });

  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) {
      document.body.removeChild(overlay);
    }
  });
}

// Logout confirmation popup
document.addEventListener('DOMContentLoaded', function() {
  const logoutBtn = document.getElementById('logoutBtn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', function() {
      const overlay = document.createElement('div');
      overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.6);
        z-index: 99999;
        display: flex;
        align-items: center;
        justify-content: center;
      `;

      const popup = document.createElement('div');
      popup.style.cssText = `
        background: white;
        padding: 40px;
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        text-align: center;
        max-width: 400px;
        animation: slideUp 0.3s ease;
      `;

      popup.innerHTML = `
        <h2 style="font-size: 24px; color: #2d3748; margin-bottom: 15px;">Do you want to exit?</h2>
        <p style="color: #718096; margin-bottom: 30px; font-size: 16px;">You will be logged out of your session.</p>
        <div style="display: flex; gap: 15px; justify-content: center;">
          <button id="yesBtn" style="
            padding: 12px 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
          ">Yes</button>
          <button id="noBtn" style="
            padding: 12px 30px;
            background: #f1f5f9;
            color: #4a5568;
            border: 2px solid #e2e8f0;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
          ">No</button>
        </div>
      `;

      overlay.appendChild(popup);
      document.body.appendChild(overlay);

      document.getElementById('yesBtn').addEventListener('click', function() {
        localStorage.clear();
        window.location.href = 'login.html';
      });

      document.getElementById('noBtn').addEventListener('click', function() {
        document.body.removeChild(overlay);
      });

      overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
          document.body.removeChild(overlay);
        }
      });
       const monthRangeSelect = document.getElementById('monthRange');
  if (monthRangeSelect) {
    monthRangeSelect.addEventListener('change', function() {
      const selectedMonth = this.value;
      const tbody = document.getElementById('entryTableBody');
      const rows = tbody.querySelectorAll('tr');
      
      if (selectedMonth) {
        const startDate = getStartDateForMonth(selectedMonth);
        
        // Update ALL existing rows dates to sequential dates starting from 21st
        rows.forEach((row, index) => {
          const rowId = row.dataset.rowId;
          const dateInput = row.querySelector(`input[name="date_${rowId}"]`);
          if (dateInput) {
            if (index === 0) {
              // First row gets the 21st
              dateInput.value = startDate;
            } else {
              // Subsequent rows get sequential dates
              const prevRow = rows[index - 1];
              const prevRowId = prevRow.dataset.rowId;
              const prevDateInput = prevRow.querySelector(`input[name="date_${prevRowId}"]`);
              if (prevDateInput && prevDateInput.value) {
                dateInput.value = getNextDate(prevDateInput.value);
              }
            }
          }
        });
      }
    });
  }
    });
  }
});

// Simple function for HTML onchange
function checkFileCount(input) {
  if (input.files.length > 1) {
    alert("Only one PDF allowed.");
    input.value = "";
  }
}

// Update Submit Button Visibility
function updateSubmitButtonVisibility() {
  const allForms = document.querySelectorAll('.ope-form');
  
  allForms.forEach((form, index) => {
    const submitBtn = form.querySelector('.submit-btn');
    if (submitBtn) {
      if (index === allForms.length - 1) {
        // Last form - show button
        submitBtn.style.display = 'inline-block';
      } else {
        // Not last form - hide button
        submitBtn.style.display = 'none';
      }
    }
  });
}


// MAIN INITIALIZATION - UPDATED
document.addEventListener("DOMContentLoaded", () => {
  // AUTH CHECK
  const token = localStorage.getItem("access_token");
  const empCode = localStorage.getItem("employee_code");
  
  if (!token || !empCode) {
    console.error("❌ No token or employee code found");
    window.location.href = "login.html";
    return;
  }

  console.log("✅ Token found:", token.substring(0, 20) + "...");
  console.log("✅ Employee Code:", empCode);

  // EMPLOYEE DETAILS FETCH
  async function loadEmployeeDetails() {
    try {
      console.log("📡 Fetching employee details...");
      const res = await fetch(`${API_URL}/api/employee/${empCode}`, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      if (!res.ok) {
        const err = await res.text();
        console.error("❌ API FAILED:", res.status, err);
        return;
      }

      const data = await res.json();
      console.log("✅ Employee data received:", data);

      const setText = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val ?? "-";
      };

      setText("empId", data.employee_id);
      setText("empName", data.employee_name);
      setText("empDesignation", data.designation);
      setText("empGender", data.gender);
      setText("empPartner", data.partner);
      setText("empManager", data.reporting_manager_name);

    } catch (err) {
      console.error("❌ Fetch crashed:", err);
    }
  }

  loadEmployeeDetails();
  
  // ✅ Setup navigation
  setupNavigation();
  checkUserRole();

  // ✅ NEW: Month range change listener - Load saved entries
  const monthRangeSelect = document.getElementById('monthRange');
  if (monthRangeSelect) {
    monthRangeSelect.addEventListener('change', async function() {
      const selectedMonth = this.value;
      const tbody = document.getElementById('entryTableBody');
      
      if (selectedMonth) {
        const startDate = getStartDateForMonth(selectedMonth);
        
        console.log("📅 Month changed to:", selectedMonth);
        
        // ✅ First, try to load saved entries
        await loadSavedEntries();
        
        // ✅ If no saved entries, add blank row
        const rows = tbody.querySelectorAll('tr');
        if (rows.length === 0) {
          console.log("No saved entries, adding blank row");
          addNewEntryRow();
        }
        
        showSuccessPopup(`Date range updated to ${monthRanges[selectedMonth].display}`);
      }
    });
  }
});

// ADD NEW ENTRY FORM
function addNewEntryFormWithToken(token, empCode) {
  const allForms = document.querySelectorAll('.ope-form');
  allForms.forEach(form => {
    form.classList.add('collapsed');
    form.classList.remove('expanded');
  });
  
  formCounter++;
  
  const mainContainer = document.querySelector('.main-container');
  const originalForm = document.querySelector('.ope-form');
  
  const newForm = originalForm.cloneNode(true);
  newForm.classList.add('additional-form', 'expanded');
  newForm.classList.remove('collapsed');
  
  const heading = newForm.querySelector('h2');
  if (heading) heading.textContent = `Entry #${formCounter}`;
  
  // Add remove button
  const removeBtn = document.createElement('button');
  removeBtn.type = 'button';
  removeBtn.className = 'remove-form-btn';
  removeBtn.innerHTML = '<i class="fas fa-times"></i>';
  removeBtn.onclick = function() {
    newForm.remove();
    formCounter--;
    updateFormNumbers();
    updateSubmitButtonVisibility();
    
    const remainingForms = document.querySelectorAll('.ope-form');
    if (remainingForms.length > 0) {
      const lastForm = remainingForms[remainingForms.length - 1];
      lastForm.classList.remove('collapsed');
      lastForm.classList.add('expanded');
    }
  };
  newForm.insertBefore(removeBtn, newForm.firstChild);
  
  // Clear all inputs
  const inputs = newForm.querySelectorAll('input, select, textarea');
  inputs.forEach(input => {
    if (input.type === 'date') {
      input.value = today;
    } else if (input.type === 'file') {
      input.value = '';
    } else if (input.tagName === 'SELECT') {
      input.selectedIndex = 0;
    } else {
      input.value = '';
    }
  });
  
  const fileNameDisplay = newForm.querySelector('#fileName');
  if (fileNameDisplay) fileNameDisplay.textContent = '';
  
  const errorMsg = newForm.querySelector('#formError');
  if (errorMsg) errorMsg.textContent = '';
  
  const formId = `dailyForm${formCounter}`;
  const formElement = newForm.querySelector('form');
  if (formElement) formElement.id = formId;
  
  newForm.addEventListener('click', function(e) {
    if (e.target.closest('input, select, textarea, button')) return;
    
    if (this.classList.contains('collapsed')) {
      document.querySelectorAll('.ope-form').forEach(f => {
        f.classList.add('collapsed');
        f.classList.remove('expanded');
      });
      
      this.classList.remove('collapsed');
      this.classList.add('expanded');
    }
  });
  
  mainContainer.appendChild(newForm);
  
  setTimeout(() => {
    newForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 100);
  
  // ATTACH LISTENERS
  attachFormListeners(newForm, token, empCode);
  
  // Update submit button visibility
  updateSubmitButtonVisibility();
}

function updateFormNumbers() {
  const forms = document.querySelectorAll('.ope-form');
  forms.forEach((form, index) => {
    const heading = form.querySelector('h2');
    if (heading) {
      if (index === 0) {
        heading.textContent = 'Entry #1';
      } else {
        heading.textContent = `Entry #${index + 1}`;
      }
    }
  });
}

// ATTACH FORM LISTENERS
function attachFormListeners(formElement, token, empCode) {
  const form = formElement.querySelector('form');
  const fileInput = formElement.querySelector('#ticketpdf');
  const fileName = formElement.querySelector('#fileName');
  
  console.log("🔗 Attaching listeners to form");
  
  // File validation
  if (fileInput) {
    fileInput.addEventListener('change', function(e) {
      if (e.target.files.length > 1) {
        showErrorPopup('Only one PDF allowed.');
        e.target.value = '';
        if (fileName) fileName.textContent = '';
        return;
      }
      
      const file = e.target.files[0];
      if (!file) {
        if (fileName) fileName.textContent = '';
        return;
      }
      
      if (file.type !== 'application/pdf') {
        if (fileName) {
          fileName.textContent = '❌ Only PDF files allowed!';
          fileName.style.color = '#e53e3e';
        }
        e.target.value = '';
      } else {
        if (fileName) {
          fileName.textContent = '✅ ' + file.name;
          fileName.style.color = '#27ae60';
        }
      }
    });
  }
  
  // Form submission - SUBMIT ALL FORMS
  if (form) {
    form.addEventListener('submit', async function(e) {
      e.preventDefault();
      
      console.log("📤 Submitting ALL forms...");
      
      const allForms = document.querySelectorAll('.ope-form');
      const submitBtn = formElement.querySelector('.submit-btn');
      
      // Disable submit button
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitting All Entries...';
      }
      
      let successCount = 0;
      let errorCount = 0;
      let errors = [];
      
      // Loop through all forms and submit
      for (let i = 0; i < allForms.length; i++) {
        const currentForm = allForms[i];
        const error = currentForm.querySelector('#formError');
        
        // Get form values
        const date = currentForm.querySelector('#date')?.value;
        const client = currentForm.querySelector('#client')?.value.trim();
        const projectId = currentForm.querySelector('#projectid')?.value.trim();
        const projectName = currentForm.querySelector('#projectname')?.value.trim();
        const locationFrom = currentForm.querySelector('#locationfrom')?.value.trim();
        const locationTo = currentForm.querySelector('#locationto')?.value.trim();
        const travelMode = currentForm.querySelector('#travelmode')?.value;
        const amount = parseFloat(currentForm.querySelector('#amount')?.value);
        const remarks = currentForm.querySelector('#remarks')?.value.trim();
        const monthRangeInput = document.getElementById('monthRange');
        const monthRange = monthRangeInput ? monthRangeInput.value : '';
        const pdfInput = currentForm.querySelector('#ticketpdf');
        const pdfFile = pdfInput?.files[0];
        
        if (error) error.textContent = '';
        
        // Validations
        if (!date || !client || !projectId || !projectName || !locationFrom || !locationTo || !travelMode || isNaN(amount) || amount <= 0 || !monthRange) {
          errors.push(`Entry #${i + 1}: Please fill all required fields`);
          errorCount++;
          continue;
        }
        
        if (travelMode === 'meter_auto' && remarks === '') {
          errors.push(`Entry #${i + 1}: Remarks required for "Meter Auto"`);
          errorCount++;
          continue;
        }
        
        if (pdfFile && pdfFile.type !== 'application/pdf') {
          errors.push(`Entry #${i + 1}: Only PDF files allowed`);
          errorCount++;
          continue;
        }
        
        // Prepare data
        const formData = new FormData();
        formData.append('date', date);
        formData.append('client', client);
        formData.append('project_id', projectId);
        formData.append('project_name', projectName);
        formData.append('location_from', locationFrom);
        formData.append('location_to', locationTo);
        formData.append('travel_mode', travelMode);
        formData.append('amount', amount);
        formData.append('remarks', remarks || 'NA');
        formData.append('month_range', monthRange);
        
        if (pdfFile) {
          formData.append('ticket_pdf', pdfFile);
        }
        
        try {
          console.log(`🚀 Submitting Entry #${i + 1}...`);
          
          const response = await fetch(`${API_URL}/api/ope/submit`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`
            },
            body: formData
          });
          
          const result = await response.json();
          
          if (response.ok) {
            console.log(`✅ Entry #${i + 1} submitted successfully`);
            successCount++;
            
            // Clear the form
            currentForm.querySelector('form').reset();
            const fileNameDisplay = currentForm.querySelector('#fileName');
            if (fileNameDisplay) fileNameDisplay.textContent = '';
            
            // Set date to today again
            const dateInput = currentForm.querySelector('#date');
            if (dateInput) dateInput.value = today;
            
          } else {
            console.error(`❌ Entry #${i + 1} failed:`, result);
            errors.push(`Entry #${i + 1}: ${result.detail || 'Submission failed'}`);
            errorCount++;
          }
        } catch (err) {
          console.error(`❌ Entry #${i + 1} error:`, err);
          errors.push(`Entry #${i + 1}: Network error`);
          errorCount++;
        }
      }
      
      // Re-enable submit button
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Entry';
      }
      
      // Show result popup
      if (errorCount === 0) {
        showSuccessPopup(`All ${successCount} entries submitted successfully!`);
        
        // Remove all additional forms, keep only first one
        const allFormsAfterSubmit = document.querySelectorAll('.ope-form');
        allFormsAfterSubmit.forEach((f, index) => {
          if (index > 0) {
            f.remove();
          }
        });
        
        // Reset form counter
        formCounter = 1;
        
        // Expand first form and update heading
        // const firstForm = document.querySelector('.ope-form');
        // if (firstForm) {
        //   firstForm.classList.add('expanded');
        //   firstForm.classList.remove('collapsed');
        //   const heading = firstForm.querySelector('h2');
        //   if (heading) heading.textContent = 'Entry #1';
        // }
        
        // Update submit button visibility
        updateSubmitButtonVisibility();
        
      } else if (successCount > 0) {
        showErrorPopup(`${successCount} entries submitted successfully, ${errorCount} failed.<br><br>${errors.join('<br>')}`);
      } else {
        showErrorPopup(`All submissions failed:<br><br>${errors.join('<br>')}`);
      }
    });
  }
}

// ========== HISTORY SECTION CODE - ADD THIS TO script.js ==========

// Travel Mode Options
// History Section Functions - Backend se data frontend pe show karne ke liye

// Travel Modes Configuration
const travelModes = [
    { value: 'metro_recharge', label: 'Metro Recharge' },
    { value: 'metro_pass', label: 'Metro Pass' },
    { value: 'metro_tickets', label: 'Metro Tickets' },
    { value: 'shared_auto', label: 'Shared Auto' },
    { value: 'shared_taxi', label: 'Shared Taxi' },
    { value: 'meter_auto', label: 'Meter Auto' },
    { value: 'taxi_cab', label: 'Taxi / Cab' },
    { value: 'bus_ticket', label: 'Bus Tickets' },
    { value: 'bus_pass', label: 'Bus Pass' },
    { value: 'train_pass 1st', label: 'Train Pass - 1st Class' },
    { value: 'train_pass 2nd', label: 'Train Pass - 2nd Class' },
    { value: 'train_ticket', label: 'Train Ticket' }
];


// UPDATED: Load history from Temp_OPE_data (editable) and OPE_data (non-editable)

async function loadHistoryData(token, empCode) {
    try {
        console.log("📡 Fetching history for:", empCode);
        
        document.getElementById('loadingDiv').style.display = 'block';
        document.getElementById('historyTableSection').style.display = 'none';
        document.getElementById('noDataDiv').style.display = 'none';

        // ✅ Fetch from Temp_OPE_data (editable)
        console.log("🔍 Fetching temp data...");
        const tempResponse = await fetch(`${API_URL}/api/ope/temp-history/${empCode}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        // Fetch from OPE_data (submitted, non-editable)
        console.log("🔍 Fetching submitted data...");
        const response = await fetch(`${API_URL}/api/ope/history/${empCode}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!tempResponse.ok && !response.ok) {
            throw new Error('Failed to fetch history');
        }

        const tempData = tempResponse.ok ? await tempResponse.json() : { history: [] };
        const data = response.ok ? await response.json() : { history: [] };
        
        console.log("✅ Temp API Response:", tempData);
        console.log("✅ Submitted API Response:", data);
        
        allHistoryData = {
            temp: tempData.history || [],
            submitted: data.history || []
        };
        
        console.log("✅ allHistoryData set:", allHistoryData);
        console.log("📊 Temp entries:", allHistoryData.temp.length);
        console.log("📊 Submitted entries:", allHistoryData.submitted.length);

        populateMonthFilter();
        
        // ✅ REMOVED: Don't call displayHistoryTable here - let the caller handle it
        
        hideLoading();

    } catch (error) {
        console.error('❌ Error loading history:', error);
        document.getElementById('loadingDiv').style.display = 'none';
        showNoData();
    }
}

// 2. Month Filter Dropdown Populate karne ka function
function populateMonthFilter() {
    const monthSet = new Set();
    
    // ✅ UPDATED: Handle new data structure
    const tempData = allHistoryData.temp || [];
    const submittedData = allHistoryData.submitted || [];
    
    tempData.forEach(item => {
        if (item.month_range) monthSet.add(item.month_range);
    });
    
    submittedData.forEach(item => {
        if (item.month_range) monthSet.add(item.month_range);
    });

    const select = document.getElementById('monthRangeFilter');
    select.innerHTML = '<option value="">All Months</option>';

    Array.from(monthSet).sort().forEach(month => {
        const option = document.createElement('option');
        option.value = month;
        option.textContent = month;
        select.appendChild(option);
    });

    select.addEventListener('change', function() {
        const selectedMonth = this.value;
        
        if (selectedMonth === '') {
            displayHistoryTable(allHistoryData);
        } else {
            // Filter both temp and submitted data
            const filteredData = {
                temp: tempData.filter(item => item.month_range === selectedMonth),
                submitted: submittedData.filter(item => item.month_range === selectedMonth)
            };
            displayHistoryTable(filteredData);
        }
    });
}

// UPDATED: Display both temporary (editable) and submitted (non-editable) entries

function displayHistoryTable(data) {
  console.log("🎨 displayHistoryTable called");
  
  const tbody = document.getElementById('historyTableBody');
  
  if (!tbody) {
    console.error("❌ historyTableBody not found in DOM!");
    return;
  }

  tbody.innerHTML = '';
  
  // ✅ ONLY SHOW SUBMITTED DATA, NOT TEMP
  let submittedData = [];
  
  if (data && typeof data === 'object') {
    if (data.submitted) {
      submittedData = data.submitted || [];
    } else if (Array.isArray(data)) {
      submittedData = data;
    }
  }
  
  console.log(`📊 Submitted entries: ${submittedData.length}`);
  
  if (submittedData.length === 0) {
    console.log("📭 No data to display");
    showNoData();
    return;
  }

  // Show submitted entries only
  submittedData.forEach((entry) => {
    const row = document.createElement('tr');
    row.dataset.entryId = entry._id;
    row.dataset.monthRange = entry.month_range;

    row.innerHTML = `
      <td>${entry.date || '-'}</td>
      <td>
        <span style="
          background: #10b981;
          color: white;
          padding: 4px 8px;
          border-radius: 6px;
          font-size: 12px;
          font-weight: 600;
        ">✓ SUBMITTED</span>
      </td>
      <td>${entry.client || '-'}</td>
      <td>${entry.project_id || '-'}</td>
      <td>${entry.project_name || '-'}</td>
      <td>${entry.project_type || '-'}</td>
      <td>${entry.location_from || '-'}</td>
      <td>${entry.location_to || '-'}</td>
      <td>${getTravelModeLabel(entry.travel_mode)}</td>
      <td>₹${entry.amount || 0}</td>
      <td>${entry.remarks || 'NA'}</td>
      <td>
        ${entry.ticket_pdf 
          ? `<button class="view-pdf-btn" onclick="viewPdf('${entry._id}', false)">
              <i class="fas fa-file-pdf"></i> View
             </button>` 
          : '-'}
      </td>
      <td style="color: #9ca3af;">
        <i class="fas fa-lock"></i> Locked
      </td>
    `;

    tbody.appendChild(row);
  });

  const loadingDiv = document.getElementById('loadingDiv');
  const tableSection = document.getElementById('historyTableSection');
  const noDataDiv = document.getElementById('noDataDiv');
  
  if (loadingDiv) loadingDiv.style.display = 'none';
  if (noDataDiv) noDataDiv.style.display = 'none';
  
  if (tableSection) {
    tableSection.style.display = 'block';
    tableSection.style.visibility = 'visible';
    tableSection.style.opacity = '1';
  }
}

// 4. Travel Mode ka Label get karne ka function
function getTravelModeLabel(value) {
    const mode = travelModes.find(m => m.value === value);
    return mode ? mode.label : value;
}

// 5. PDF View karne ka function
window.viewPdf = function(entryId) {
    const entry = allHistoryData.find(e => e._id === entryId);
    
    if (entry && entry.ticket_pdf) {
        openPdfModal(entry.ticket_pdf);
    } else {
        showErrorPopup('PDF not available');
    }
};

// ✅ NEW: Edit temporary entry
window.editTempRow = function(entryId) {
    const row = document.querySelector(`tr[data-entry-id="${entryId}"]`);
    if (!row) return;

    const tempData = allHistoryData.temp || [];
    const entry = tempData.find(e => e._id === entryId);
    if (!entry) return;

    // Save original data for cancel
    originalRowData[entryId] = { ...entry };

    // Make row editable
    row.innerHTML = `
        <td><input type="date" value="${entry.date}" id="edit_date_${entryId}" /></td>
        <td><span style="background: #fbbf24; color: #78350f; padding: 4px 8px; border-radius: 6px; font-size: 12px;">EDITING</span></td>
        <td><input type="text" value="${entry.client}" id="edit_client_${entryId}" /></td>
        <td><input type="text" value="${entry.project_id}" id="edit_projectid_${entryId}" /></td>
        <td><input type="text" value="${entry.project_name}" id="edit_projectname_${entryId}" /></td>
        <td>
            <select id="edit_projecttype_${entryId}">
                <option value="Concurrent" ${entry.project_type === 'Concurrent' ? 'selected' : ''}>Concurrent</option>
                <option value="KYC" ${entry.project_type === 'KYC' ? 'selected' : ''}>KYC</option>
                <option value="IFC" ${entry.project_type === 'IFC' ? 'selected' : ''}>IFC</option>
                <option value="Statutory" ${entry.project_type === 'Statutory' ? 'selected' : ''}>Statutory</option>
                <option value="Internal" ${entry.project_type === 'Internal' ? 'selected' : ''}>Internal</option>
                <option value="Cyber Security" ${entry.project_type === 'Cyber Security' ? 'selected' : ''}>Cyber Security</option>
                <option value="Consulting" ${entry.project_type === 'Consulting' ? 'selected' : ''}>Consulting</option>
                <option value="Outsourcing" ${entry.project_type === 'Outsourcing' ? 'selected' : ''}>Outsourcing</option>
                <option value="Other" ${entry.project_type === 'Other' ? 'selected' : ''}>Other</option>
            </select>
        </td>
        <td><input type="text" value="${entry.location_from}" id="edit_from_${entryId}" /></td>
        <td><input type="text" value="${entry.location_to}" id="edit_to_${entryId}" /></td>
        <td>
            <select id="edit_mode_${entryId}">
                ${travelModes.map(m => 
                    `<option value="${m.value}" ${m.value === entry.travel_mode ? 'selected' : ''}>
                        ${m.label}
                    </option>`
                ).join('')}
            </select>
        </td>
        <td><input type="number" value="${entry.amount}" id="edit_amount_${entryId}" min="0" step="0.01" /></td>
        <td><input type="text" value="${entry.remarks || ''}" id="edit_remarks_${entryId}" /></td>
        <td>-</td>
        <td class="action-btns">
            <button class="save-btn" onclick="saveTempRow('${entryId}', '${entry.month_range}')">
                <i class="fas fa-save"></i> Save
            </button>
            <button class="cancel-btn" onclick="cancelTempEdit('${entryId}')">
                <i class="fas fa-times"></i> Cancel
            </button>
        </td>
    `;
};

// ✅ NEW: Save edited temporary entry
window.saveTempRow = async function(entryId, monthRange) {
    const token = localStorage.getItem('access_token');
    
    const updatedData = {
        date: document.getElementById(`edit_date_${entryId}`).value,
        client: document.getElementById(`edit_client_${entryId}`).value.trim(),
        project_id: document.getElementById(`edit_projectid_${entryId}`).value.trim(),
        project_name: document.getElementById(`edit_projectname_${entryId}`).value.trim(),
        project_type: document.getElementById(`edit_projecttype_${entryId}`).value,
        location_from: document.getElementById(`edit_from_${entryId}`).value.trim(),
        location_to: document.getElementById(`edit_to_${entryId}`).value.trim(),
        travel_mode: document.getElementById(`edit_mode_${entryId}`).value,
        amount: parseFloat(document.getElementById(`edit_amount_${entryId}`).value),
        remarks: document.getElementById(`edit_remarks_${entryId}`).value.trim()
    };

    // Validation
    if (!updatedData.date || !updatedData.client || !updatedData.project_id || 
        !updatedData.project_name || !updatedData.project_type || 
        !updatedData.location_from || !updatedData.location_to || 
        !updatedData.travel_mode || isNaN(updatedData.amount) || updatedData.amount <= 0) {
        showErrorPopup('Please fill all fields correctly');
        return;
    }

    try {
        const response = await fetch(`${API_URL}/api/ope/update-temp/${entryId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                ...updatedData,
                month_range: monthRange
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Update failed');
        }

        showSuccessPopup('Entry updated successfully!');
        
        const empCode = localStorage.getItem('employee_code');
        await loadHistoryData(token, empCode);
        displayHistoryTable(allHistoryData);
        
    } catch (error) {
        console.error('Error updating:', error);
        showErrorPopup(error.message || 'Network error');
    }
};

// ✅ NEW: Cancel temp edit
window.cancelTempEdit = function(entryId) {
    const empCode = localStorage.getItem('employee_code');
    const token = localStorage.getItem('access_token');
    loadHistoryData(token, empCode).then(() => {
        displayHistoryTable(allHistoryData);
    });
};

// ✅ NEW: Delete temporary entry
window.deleteTempRow = async function(entryId, monthRange) {
    if (!confirm('Are you sure you want to delete this saved entry?')) {
        return;
    }

    const token = localStorage.getItem('access_token');

    try {
        const response = await fetch(`${API_URL}/api/ope/delete-temp/${entryId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ month_range: monthRange })
        });

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Delete failed: ${response.status}`);
        }

        showSuccessPopup('Entry deleted successfully!');

        const empCode = localStorage.getItem('employee_code');
        await loadHistoryData(token, empCode);
        displayHistoryTable(allHistoryData);

    } catch (error) {
        console.error('Delete error:', error);
        showErrorPopup(error.message || 'Failed to delete entry');
    }
};

// ✅ UPDATED: View PDF (handle both temp and submitted)
// ✅ UPDATED: View PDF with proper data source checking
window.viewPdf = function(entryId, isTemp = false) {
    console.log("📄 Viewing PDF for entry:", entryId, "isTemp:", isTemp);
    
    let entry = null;
    
    // ✅ Check in different data sources based on context
    if (isTemp) {
        // Check in temp data
        const tempData = allHistoryData.temp || [];
        entry = tempData.find(e => e._id === entryId);
    } else {
        // Check in all possible sources
        
        // 1. Check in submitted/history data
        if (allHistoryData.submitted) {
            entry = allHistoryData.submitted.find(e => e._id === entryId);
        }
        
        // 2. Check in approved data
        if (!entry && typeof allApproveData !== 'undefined') {
            entry = allApproveData.find(e => e._id === entryId);
        }
        
        // 3. Check in rejected data
        if (!entry && typeof allRejectData !== 'undefined') {
            entry = allRejectData.find(e => e._id === entryId);
        }
        
        // 4. Check in pending data (if exists)
        if (!entry && typeof allPendingData !== 'undefined') {
            entry = allPendingData.find(e => e._id === entryId);
        }
    }
    
    console.log("📦 Entry found:", entry ? "Yes" : "No");
    
    if (entry && entry.ticket_pdf) {
        console.log("✅ Opening PDF modal");
        openPdfModal(entry.ticket_pdf);
    } else {
        console.error("❌ PDF not found for entry:", entryId);
        showErrorPopup('PDF not available for this entry');
    }
};

// 6. PDF Modal Open karne ka function
function openPdfModal(base64Pdf) {
    const modal = document.getElementById('pdfModal');
    const viewer = document.getElementById('pdfViewer');
    
    viewer.src = `data:application/pdf;base64,${base64Pdf}`;
    modal.classList.add('active');
}

// 7. PDF Modal Close karne ka function
function closePdfModal() {
    const modal = document.getElementById('pdfModal');
    modal.classList.remove('active');
    
    document.getElementById('pdfViewer').src = '';
}

window.closePdfModal = closePdfModal;

// 8. Row Edit karne ka function
window.editRow = function(entryId) {
    const row = document.querySelector(`tr[data-entry-id="${entryId}"]`);
    if (!row) return;

    const entry = allHistoryData.find(e => e._id === entryId);
    if (!entry) return;

    // Original data save karo (cancel ke liye)
    originalRowData[entryId] = { ...entry };

    // Row ko editable banao
    row.innerHTML = `
        <td><input type="date" value="${entry.date}" id="edit_date_${entryId}" /></td>
        <td><input type="text" value="${entry.client}" id="edit_client_${entryId}" /></td>
        <td><input type="text" value="${entry.project_id}" id="edit_projectid_${entryId}" /></td>
        <td><input type="text" value="${entry.project_name}" id="edit_projectname_${entryId}" /></td>
        <td><input type="text" value="${entry.location_from}" id="edit_from_${entryId}" /></td>
        <td><input type="text" value="${entry.location_to}" id="edit_to_${entryId}" /></td>
        <td>
            <select id="edit_mode_${entryId}">
                ${travelModes.map(m => 
                    `<option value="${m.value}" ${m.value === entry.travel_mode ? 'selected' : ''}>
                        ${m.label}
                    </option>`
                ).join('')}
            </select>
        </td>
        <td><input type="number" value="${entry.amount}" id="edit_amount_${entryId}" min="0" step="0.01" /></td>
        <td><input type="text" value="${entry.remarks || ''}" id="edit_remarks_${entryId}" /></td>
        <td>-</td>
        <td class="action-btns">
            <button class="save-btn" onclick="saveRow('${entryId}', '${entry.month_range}')">
                <i class="fas fa-save"></i> Save
            </button>
            <button class="cancel-btn" onclick="cancelEdit('${entryId}')">
                <i class="fas fa-times"></i> Cancel
            </button>
        </td>
    `;
};

// 9. Edit Cancel karne ka function
window.cancelEdit = function(entryId) {
    const original = originalRowData[entryId];
    if (!original) return;

    const row = document.querySelector(`tr[data-entry-id="${entryId}"]`);
    if (!row) return;

    // Original data wapas show karo
    row.innerHTML = `
        <td>${original.date || '-'}</td>
        <td>${original.client || '-'}</td>
        <td>${original.project_id || '-'}</td>
        <td>${original.project_name || '-'}</td>
        <td>${original.location_from || '-'}</td>
        <td>${original.location_to || '-'}</td>
        <td>${getTravelModeLabel(original.travel_mode)}</td>
        <td>₹${original.amount || 0}</td>
        <td>${original.remarks || 'NA'}</td>
        <td>
            ${original.ticket_pdf 
                ? `<button class="view-pdf-btn" onclick="viewPdf('${original._id}')">
                    <i class="fas fa-file-pdf"></i> View
                   </button>` 
                : '-'}
        </td>
        <td class="action-btns">
            <button class="edit-btn" onclick="editRow('${original._id}')">
                <i class="fas fa-edit"></i> Edit
            </button>
            <button class="delete-btn" onclick="deleteRow('${original._id}', '${original.month_range}')">
                <i class="fas fa-trash"></i> Delete
            </button>
        </td>
    `;

    // Saved data delete karo
    delete originalRowData[entryId];
};

// 10. Row Save (Update) karne ka function
window.saveRow = async function(entryId, monthRange) {
    const token = localStorage.getItem('access_token');
    
    // Updated data collect karo
    const updatedData = {
        date: document.getElementById(`edit_date_${entryId}`).value,
        client: document.getElementById(`edit_client_${entryId}`).value.trim(),
        project_id: document.getElementById(`edit_projectid_${entryId}`).value.trim(),
        project_name: document.getElementById(`edit_projectname_${entryId}`).value.trim(),
        location_from: document.getElementById(`edit_from_${entryId}`).value.trim(),
        location_to: document.getElementById(`edit_to_${entryId}`).value.trim(),
        travel_mode: document.getElementById(`edit_mode_${entryId}`).value,
        amount: parseFloat(document.getElementById(`edit_amount_${entryId}`).value),
        remarks: document.getElementById(`edit_remarks_${entryId}`).value.trim()
    };

    // Validation
    if (!updatedData.date || !updatedData.client || !updatedData.project_id || 
        !updatedData.project_name || !updatedData.location_from || 
        !updatedData.location_to || !updatedData.travel_mode || 
        isNaN(updatedData.amount) || updatedData.amount <= 0) {
        showErrorPopup('Please fill all fields correctly');
        return;
    }

    try {
        // Backend API call
        const response = await fetch(`${API_URL}/api/ope/update/${entryId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                ...updatedData,
                month_range: monthRange
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Update failed');
        }

        showSuccessPopup('Entry updated successfully!');
        
        // Fresh data load karo
        const empCode = localStorage.getItem('employee_code');
        await loadHistoryData(token, empCode);
        
    } catch (error) {
        console.error('Error updating:', error);
        showErrorPopup(error.message || 'Network error');
    }
};

// 11. Row Delete karne ka function
window.deleteRow = async function(entryId, monthRange) {
  if (!confirm('Are you sure you want to delete this entry?')) {
    return;
  }

  if (!entryId) {
    showErrorPopup('Invalid entry ID');
    return;
  }

  const token = localStorage.getItem('access_token');

  try {
    console.log(`Deleting entry ID: ${entryId}, Month: ${monthRange}`); 

    const response = await fetch(`${API_URL}/api/ope/delete/${entryId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ month_range: monthRange })
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `Delete failed: ${response.status}`);
    }

    showSuccessPopup('Entry deleted successfully!');

    // Reload history
    const empCode = localStorage.getItem('employee_code');
    await loadHistoryData(token, empCode);

  } catch (error) {
    console.error('Delete error:', error);
    showErrorPopup(error.message || 'Failed to delete entry');
  }
};

// 12. Loading Hide karne ka function
function hideLoading() {
    document.getElementById('loadingDiv').style.display = 'none';
}

// 13. No Data Show karne ka function
function showNoData() {
    document.getElementById('loadingDiv').style.display = 'none';
    document.getElementById('historyTableSection').style.display = 'none';
    document.getElementById('noDataDiv').style.display = 'block';
}

// 14. Navigation Setup (OPE aur History ke beech switch karne ke liye)

function setupNavigation() {
  const navOPE = document.getElementById('navOPE');
  const navHistory = document.getElementById('navHistory');
  const navStatus = document.getElementById('navStatus');
  const navPending = document.getElementById('navPending');
  const navApprove = document.getElementById('navApprove');
  const navReject = document.getElementById('navReject');
  
  const opeSection = document.getElementById('opeSection');
  const historySection = document.getElementById('historySection');
  const statusSection = document.getElementById('statusSection');
  const pendingSection = document.getElementById('pendingSection');
  const approveSection = document.getElementById('approveSection');
  const rejectSection = document.getElementById('rejectSection');

  // Helper function
  function switchSection(activeNav, activeSection, loadDataCallback) {
    // Remove active from all nav items
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.remove('active');
    });
    activeNav.classList.add('active');
    
    // Hide ALL sections properly
    document.querySelectorAll('.content-section').forEach(section => {
      section.classList.remove('active');
      section.style.display = 'none';  
    });
    
    // Show selected section
    if (activeSection) {
      activeSection.classList.add('active');
      activeSection.style.display = 'block';  
    }
    
    // Close mobile menu
    if (window.innerWidth <= 768) {
      document.querySelector('.sidebar').classList.remove('mobile-active');
    }
    
    // Load data if callback provided
    if (loadDataCallback) {
      loadDataCallback();
    }
  }

  if (navOPE) {
    navOPE.addEventListener('click', function() {
      switchSection(navOPE, opeSection);
    });
  }

  // Update the navHistory click event
if (navHistory) {
    navHistory.addEventListener('click', async function() {
        console.log("📌 History nav clicked");
        
        switchSection(navHistory, historySection, async () => {
            const token = localStorage.getItem('access_token');
            const empCode = localStorage.getItem('employee_code');
            
            console.log("🔑 Token:", token ? "exists" : "missing");
            console.log("👤 EmpCode:", empCode);
            
            if (token && empCode) {
                console.log("🚀 Loading history data...");
                await loadHistoryData(token, empCode);
                
                console.log("📊 allHistoryData after load:", allHistoryData);
                
                // ✅ CRITICAL FIX: Force display table after loading
                displayHistoryTable(allHistoryData);
            } else {
                console.error("❌ Missing token or empCode");
            }
        });
    });
}

  if (navStatus) {
    navStatus.addEventListener('click', function() {
      switchSection(navStatus, statusSection);
    });
  }

  if (navPending) {
    navPending.addEventListener('click', async function() {
      switchSection(navPending, pendingSection, async () => {
        const token = localStorage.getItem('access_token');
        const empCode = localStorage.getItem('employee_code');
        
        if (token && empCode) {
          await loadPendingData(token, empCode);
        }
      });
    });
  }

  if (navApprove) {
    navApprove.addEventListener('click', async function() {
      switchSection(navApprove, approveSection, async () => {
        const token = localStorage.getItem('access_token');
        const empCode = localStorage.getItem('employee_code');
        
        if (token && empCode) {
          await loadApproveData(token, empCode);
        }
      });
    });
  }

  if (navReject) {
    navReject.addEventListener('click', async function() {
      switchSection(navReject, rejectSection, async () => {
        const token = localStorage.getItem('access_token');
        const empCode = localStorage.getItem('employee_code');
        
        if (token && empCode) {
          await loadRejectData(token, empCode);
        }
      });
    });
  }
}

// 15. Success Popup Show karne ka function
function showSuccessPopup(message) {
  const overlay = document.createElement('div');
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.6);
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    box-sizing: border-box;
  `;

  const popup = document.createElement('div');
  popup.style.cssText = `
    background: white;
    padding: 30px;
    border-radius: 16px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    text-align: center;
    max-width: 420px;
    width: calc(100% - 40px);
    box-sizing: border-box;
    animation: slideUp 0.3s ease;
  `;

  popup.innerHTML = `
    <div style="
      width: 70px;
      height: 70px;
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 18px;
    ">
      <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
        <polyline points="20 6 9 17 4 12"></polyline>
      </svg>
    </div>
    <h2 style="font-size: 21px; color: #1f2937; margin-bottom: 10px; font-weight: 600;">Success!</h2>
    <p style="color: #6b7280; font-size: 14.5px; line-height: 1.5; word-wrap: break-word; text-align: center;">${message}</p>
  `;

  overlay.appendChild(popup);
  document.body.appendChild(overlay);

  setTimeout(() => {
    if (document.body.contains(overlay)) {
      overlay.style.opacity = '0';
      overlay.style.transition = 'opacity 0.3s ease';
      setTimeout(() => {
        if (document.body.contains(overlay)) {
          document.body.removeChild(overlay);
        }
      }, 300);
    }
  }, 2500);

  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) {
      overlay.style.opacity = '0';
      overlay.style.transition = 'opacity 0.3s ease';
      setTimeout(() => {
        if (document.body.contains(overlay)) {
          document.body.removeChild(overlay);
        }
      }, 300);
    }
  });
}

// 16. Error Popup Show karne ka function
function showErrorPopup(message) {
  const overlay = document.createElement('div');
  overlay.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.6);
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    box-sizing: border-box;
  `;

  const popup = document.createElement('div');
  popup.style.cssText = `
    background: white;
    padding: 30px;
    border-radius: 16px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    text-align: center;
    max-width: 420px;
    width: calc(100% - 40px);
    max-height: 85vh;
    overflow-y: auto;
    box-sizing: border-box;
    animation: slideUp 0.3s ease;
  `;

  popup.innerHTML = `
    <div style="
      width: 70px;
      height: 70px;
      background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 18px;
    ">
      <svg width="38" height="38" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    </div>
    <h2 style="font-size: 21px; color: #1f2937; margin-bottom: 10px; font-weight: 600;">Error</h2>
    <div style="
      color: #6b7280;
      font-size: 14px;
      line-height: 1.6;
      text-align: center;
      max-height: 250px;
      overflow-y: auto;
      word-wrap: break-word;
    ">${message}</div>
  `;

  overlay.appendChild(popup);
  document.body.appendChild(overlay);

  setTimeout(() => {
    if (document.body.contains(overlay)) {
      overlay.style.opacity = '0';
      overlay.style.transition = 'opacity 0.3s ease';
      setTimeout(() => {
        if (document.body.contains(overlay)) {
          document.body.removeChild(overlay);
        }
      }, 300);
    }
  }, 3000);

  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) {
      overlay.style.opacity = '0';
      overlay.style.transition = 'opacity 0.3s ease';
      setTimeout(() => {
        if (document.body.contains(overlay)) {
          document.body.removeChild(overlay);
        }
      }, 300);
    }
  });
}

// DOMContentLoaded me navigation setup karo
document.addEventListener('DOMContentLoaded', function() {
    setupNavigation();
    checkUserRole();

    const monthRangeSelect = document.getElementById('monthRange');
  if (monthRangeSelect) {
    monthRangeSelect.addEventListener('change', function() {
      const selectedMonth = this.value;
      const tbody = document.getElementById('entryTableBody');
      const rows = tbody.querySelectorAll('tr');
      
      if (selectedMonth && rows.length > 0) {
        const startDate = getStartDateForMonth(selectedMonth);
        
        // Update ALL existing rows dates to sequential dates starting from 21st
        rows.forEach((row, index) => {
          const rowId = row.dataset.rowId;
          const dateInput = row.querySelector(`input[name="date_${rowId}"]`);
          if (dateInput) {
            if (index === 0) {
              // First row gets the 21st
              dateInput.value = startDate;
            } else {
              // Subsequent rows get sequential dates
              const prevRow = rows[index - 1];
              const prevRowId = prevRow.dataset.rowId;
              const prevDateInput = prevRow.querySelector(`input[name="date_${prevRowId}"]`);
              if (prevDateInput && prevDateInput.value) {
                dateInput.value = getNextDate(prevDateInput.value);
              }
            }
          }
        });
        
        showSuccessPopup(`Date range updated to ${monthRanges[selectedMonth].display}`);
      }
    });
  }
});



let entryCounter = 0;
let copiedRowData = null;

// Initialize first row on page load
document.addEventListener('DOMContentLoaded', function() {
  addNewEntryRow();
});

// Add New Entry Row
// Add New Entry Row - UPDATED VERSION
function addNewEntryRow() {
  entryCounter++;
  const tbody = document.getElementById('entryTableBody');
  const monthRangeSelect = document.getElementById('monthRange');
  const selectedMonth = monthRangeSelect ? monthRangeSelect.value : '';
  
  // ✅ UPDATED: Get date for new row based on month range
  let newRowDate = '';
  
  if (selectedMonth) {
    const existingRows = tbody.querySelectorAll('tr');
    
    if (existingRows.length > 0) {
      // Get last row's date and add 1 day
      const lastRow = existingRows[existingRows.length - 1];
      const lastRowId = lastRow.dataset.rowId;
      const lastDateInput = lastRow.querySelector(`input[name="date_${lastRowId}"]`);
      if (lastDateInput && lastDateInput.value) {
        newRowDate = getNextDate(lastDateInput.value);
      } else {
        newRowDate = getStartDateForMonth(selectedMonth);
      }
    } else {
      // First row - use month start date (21st)
      newRowDate = getStartDateForMonth(selectedMonth);
    }
  }
  // ✅ If no month selected, leave date empty (no error)
  
  const row = document.createElement('tr');
  row.dataset.rowId = entryCounter;
  
  row.innerHTML = `
    <td><strong>${entryCounter}</strong></td>
    <td><input type="date" name="date_${entryCounter}" value="${newRowDate}" required /></td>
    <td>
      <div class="table-action-btns">
        <button type="button" class="copy-btn" onclick="copyRow(${entryCounter})">
          <i class="fas fa-copy"></i> Copy
        </button>
        <button type="button" class="paste-btn" onclick="pasteRow(${entryCounter})">
          <i class="fas fa-paste"></i> Paste
        </button>
      </div>
    </td>
    <td><input type="text" name="client_${entryCounter}" placeholder="Client Name" required /></td>
    <td><input type="text" name="projectid_${entryCounter}" placeholder="Project ID" required /></td>
    <td><input type="text" name="projectname_${entryCounter}" placeholder="Project Name" required /></td>
    <td>
      <select name="projecttype_${entryCounter}" required>
        <option value="" disabled selected>Select Type</option>
        <option value="Concurrent">Concurrent</option>
        <option value="KYC">KYC</option>
        <option value="IFC">IFC</option>
        <option value="Statutory">Statutory</option>
        <option value="Internal">Internal</option>
        <option value="Cyber Security">Cyber Security</option>
        <option value="Consulting">Consulting</option>
        <option value="Outsourcing">Outsourcing</option>
        <option value="Other">Other</option>
      </select>
    </td>
    <td><input type="text" name="locationfrom_${entryCounter}" placeholder="From" required /></td>
    <td><input type="text" name="locationto_${entryCounter}" placeholder="To" required /></td>
    <td>
      <select name="travelmode_${entryCounter}" required>
        <option value="" disabled selected>Select Mode</option>
        <option value="metro_recharge">Metro Recharge</option>
        <option value="metro_pass">Metro Pass</option>
        <option value="metro_tickets">Metro Tickets</option>
        <option value="shared_auto">Shared Auto</option>
        <option value="shared_taxi">Shared Taxi</option>
        <option value="meter_auto">Meter Auto</option>
        <option value="taxi_cab">Taxi / Cab</option>
        <option value="bus_ticket">Bus Tickets</option>
        <option value="bus_pass">Bus Pass</option>
        <option value="train_pass 1st">Train Pass - 1st Class</option>
        <option value="train_pass 2nd">Train Pass - 2nd Class</option>
        <option value="train_ticket">Train Ticket</option>
        <option value="other">Other</option>
      </select>
    </td>
    <td><input type="number" name="amount_${entryCounter}" placeholder="Amount" min="0" step="0.01" required /></td>
    <td><input type="text" name="remarks_${entryCounter}" placeholder="Remarks" /></td>
    <td><input type="file" name="ticketpdf_${entryCounter}" accept=".pdf" /></td>
    <td>
      <button type="button" class="delete-row-btn" onclick="handleDeleteRow(${entryCounter})">
      <i class="fas fa-trash"></i> Delete
      </button>
    </td>
  `;
  
  tbody.appendChild(row);
  
  // ✅ UPDATED: Use blur instead of change - validates only after user finishes typing
  const dateInput = row.querySelector(`input[name="date_${entryCounter}"]`);
  if (dateInput) {
    dateInput.addEventListener('blur', function() {
      // Only validate if month is selected and date is entered
      const monthRangeSelect = document.getElementById('monthRange');
      const selectedMonth = monthRangeSelect ? monthRangeSelect.value : '';
      
      if (selectedMonth && this.value) {
        const isValid = validateDateInRange(this, entryCounter);
        if (!isValid) {
          // Reset to valid date after showing error
          const existingRows = tbody.querySelectorAll('tr');
          const currentRowIndex = Array.from(existingRows).indexOf(row);
          
          if (currentRowIndex === 0) {
            this.value = getStartDateForMonth(selectedMonth);
          } else {
            const prevRow = existingRows[currentRowIndex - 1];
            const prevRowId = prevRow.dataset.rowId;
            const prevDateInput = prevRow.querySelector(`input[name="date_${prevRowId}"]`);
            if (prevDateInput && prevDateInput.value) {
              this.value = getNextDate(prevDateInput.value);
            } else {
              this.value = getStartDateForMonth(selectedMonth);
            }
          }
        }
      }
    });
  }
  
  setTimeout(() => {
    row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, 100);
}

// Copy Row Data
function copyRow(rowId) {
  const row = document.querySelector(`tr[data-row-id="${rowId}"]`);
  if (!row) return;
  
  copiedRowData = {
    client: row.querySelector(`input[name="client_${rowId}"]`).value,
    projectid: row.querySelector(`input[name="projectid_${rowId}"]`).value,
    projectname: row.querySelector(`input[name="projectname_${rowId}"]`).value,
    projecttype: row.querySelector(`select[name="projecttype_${rowId}"]`).value,
    locationfrom: row.querySelector(`input[name="locationfrom_${rowId}"]`).value,
    locationto: row.querySelector(`input[name="locationto_${rowId}"]`).value,
    travelmode: row.querySelector(`select[name="travelmode_${rowId}"]`).value,
    remarks: row.querySelector(`input[name="remarks_${rowId}"]`).value
  };
  
  showSuccessPopup('Row data copied!');
}

// Paste Row Data
function pasteRow(rowId) {
  if (!copiedRowData) {
    showErrorPopup('No data copied yet!');
    return;
  }
  
  const row = document.querySelector(`tr[data-row-id="${rowId}"]`);
  if (!row) return;
  
  row.querySelector(`input[name="client_${rowId}"]`).value = copiedRowData.client;
  row.querySelector(`input[name="projectid_${rowId}"]`).value = copiedRowData.projectid;
  row.querySelector(`input[name="projectname_${rowId}"]`).value = copiedRowData.projectname;
  row.querySelector(`select[name="projecttype_${rowId}"]`).value = copiedRowData.projecttype;
  row.querySelector(`input[name="locationfrom_${rowId}"]`).value = copiedRowData.locationfrom;
  row.querySelector(`input[name="locationto_${rowId}"]`).value = copiedRowData.locationto;
  row.querySelector(`select[name="travelmode_${rowId}"]`).value = copiedRowData.travelmode;
  row.querySelector(`input[name="remarks_${rowId}"]`).value = copiedRowData.remarks;
  
  showSuccessPopup('Data pasted successfully!');
}

// Delete Entry Row
async function deleteEntryRow(rowId) {
  const row = document.querySelector(`tr[data-row-id="${rowId}"]`);
  const tbody = document.getElementById('entryTableBody');
  
  // Don't delete if it's the only row
  if (tbody.querySelectorAll('tr').length === 1) {
    showErrorPopup('Cannot delete the last entry!');
    return;
  }
  
  // ✅ UPDATED: Use custom popup
  const confirmed = await showDeleteConfirmPopup(
    'Delete this unsaved entry? This will only remove it from the form.'
  );
  
  if (!confirmed) {
    return;
  }
  
  if (row) {
    row.remove();
    
    // Renumber all S.No columns
    const remainingRows = tbody.querySelectorAll('tr');
    remainingRows.forEach((r, index) => {
      const snoCell = r.querySelector('td:first-child strong');
      if (snoCell) {
        snoCell.textContent = index + 1;
      }
    });
    
    showSuccessPopup('Entry row deleted!');
  }
}




// Handle delete - check if saved or unsaved
async function handleDeleteRow(rowId) {
  const row = document.querySelector(`tr[data-row-id="${rowId}"]`);
  if (!row) return;
  
  const savedEntryId = row.dataset.savedEntryId;
  const monthRangeSelect = document.getElementById('monthRange');
  const monthRange = monthRangeSelect ? monthRangeSelect.value : '';
  
  // If entry is saved, delete from database
  if (savedEntryId) {
    await deleteSavedRow(rowId, savedEntryId, monthRange);
  } else {
    // If entry not saved, just remove from UI
    deleteEntryRow(rowId);
  }
}

// ✅ NEW: Confirmation Popup for Delete
function showDeleteConfirmPopup(message) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.6);
      z-index: 99999;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      animation: fadeIn 0.2s ease;
    `;

    const popup = document.createElement('div');
    popup.style.cssText = `
      background: white;
      padding: 35px 30px;
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
      text-align: center;
      max-width: 450px;
      width: 90%;
      animation: slideUp 0.3s ease;
    `;

    popup.innerHTML = `
      <div style="
        width: 80px;
        height: 80px;
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 20px;
        animation: scaleIn 0.4s ease;
      ">
        <i class="fas fa-trash-alt" style="font-size: 36px; color: white;"></i>
      </div>
      <h2 style="font-size: 22px; color: #1f2937; margin-bottom: 12px; font-weight: 600;">Delete Entry?</h2>
      <p style="color: #6b7280; margin-bottom: 28px; font-size: 15px; line-height: 1.5;">${message}</p>
      <div style="display: flex; gap: 12px; justify-content: center;">
        <button id="confirmDeleteBtn" style="
          padding: 12px 28px;
          background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
          color: white;
          border: none;
          border-radius: 10px;
          font-size: 15px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.3s ease;
          box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
          display: flex;
          align-items: center;
          gap: 8px;
        ">
          <i class="fas fa-check"></i> Yes, Delete
        </button>
        <button id="cancelDeleteBtn" style="
          padding: 12px 28px;
          background: #f1f5f9;
          color: #4a5568;
          border: 2px solid #e2e8f0;
          border-radius: 10px;
          font-size: 15px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.3s ease;
          display: flex;
          align-items: center;
          gap: 8px;
        ">
          <i class="fas fa-times"></i> Cancel
        </button>
      </div>
    `;

    overlay.appendChild(popup);
    document.body.appendChild(overlay);

    // Button hover effects
    const confirmBtn = document.getElementById('confirmDeleteBtn');
    const cancelBtn = document.getElementById('cancelDeleteBtn');

    confirmBtn.addEventListener('mouseenter', () => {
      confirmBtn.style.transform = 'translateY(-2px)';
      confirmBtn.style.boxShadow = '0 6px 16px rgba(239, 68, 68, 0.4)';
    });
    confirmBtn.addEventListener('mouseleave', () => {
      confirmBtn.style.transform = 'translateY(0)';
      confirmBtn.style.boxShadow = '0 4px 12px rgba(239, 68, 68, 0.3)';
    });

    cancelBtn.addEventListener('mouseenter', () => {
      cancelBtn.style.background = '#e2e8f0';
      cancelBtn.style.transform = 'translateY(-2px)';
    });
    cancelBtn.addEventListener('mouseleave', () => {
      cancelBtn.style.background = '#f1f5f9';
      cancelBtn.style.transform = 'translateY(0)';
    });

    // Confirm button click
    confirmBtn.addEventListener('click', () => {
      overlay.style.opacity = '0';
      overlay.style.transition = 'opacity 0.2s ease';
      setTimeout(() => {
        if (document.body.contains(overlay)) {
          document.body.removeChild(overlay);
        }
      }, 200);
      resolve(true);
    });

    // Cancel button click
    cancelBtn.addEventListener('click', () => {
      overlay.style.opacity = '0';
      overlay.style.transition = 'opacity 0.2s ease';
      setTimeout(() => {
        if (document.body.contains(overlay)) {
          document.body.removeChild(overlay);
        }
      }, 200);
      resolve(false);
    });

    // Close on overlay click
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.style.opacity = '0';
        overlay.style.transition = 'opacity 0.2s ease';
        setTimeout(() => {
          if (document.body.contains(overlay)) {
            document.body.removeChild(overlay);
          }
        }, 200);
        resolve(false);
      }
    });
  });
}

// ✅ UPDATED: Only show error if date is truly invalid
function validateDateInRange(dateInput, rowId) {
  const monthRangeSelect = document.getElementById('monthRange');
  const selectedMonth = monthRangeSelect ? monthRangeSelect.value : '';
  
  // Don't validate if no month selected
  if (!selectedMonth) {
    return true; // Allow any date if month not selected yet
  }
  
  const selectedDate = dateInput.value;
  
  // Don't validate if no date entered yet
  if (!selectedDate) {
    return true; // Allow empty date
  }
  
  // Check if date is in valid range
  if (!isDateInMonthRange(selectedDate, selectedMonth)) {
    const range = monthRanges[selectedMonth];
    showErrorPopup(
      `❌ Invalid Date!<br><br>` +
      `Selected date: <strong>${selectedDate}</strong><br>` +
      `Valid range: <strong>${range.start}</strong> to <strong>${range.end}</strong><br><br>` +
      `Please select a date within <strong>${range.display}</strong> payroll period.`
    );
    return false;
  }
  
  return true;
}


// ✅ UPDATED: Save validation with better error handling
// ============================================
// SAVE ALL ENTRIES (Store in Temp, Keep in Form)
// ============================================
async function saveAllEntries() {
  const token = localStorage.getItem('access_token');
  const empCode = localStorage.getItem('employee_code');
  
  if (!token || !empCode) {
    showErrorPopup('Authentication required. Please login again.');
    return;
  }
  
  const monthRangeSelect = document.getElementById('monthRange');
  const monthRange = monthRangeSelect ? monthRangeSelect.value : '';
  
  if (!monthRange) {
    showErrorPopup('Please select month range first!');
    return;
  }
  
  const tbody = document.getElementById('entryTableBody');
  const rows = tbody.querySelectorAll('tr');
  
  if (rows.length === 0) {
    showErrorPopup('No entries to save!');
    return;
  }
  
  const saveBtn = document.querySelector('.btn-primary');
  if (saveBtn) {
    saveBtn.disabled = true;
    saveBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Saving...';
  }
  
  let successCount = 0;
  let errorCount = 0;
  let errors = [];
  
  // Format month_range
  function format_month_range(month_str) {
    try {
      const parts = month_str.toLowerCase().split('-');
      const month_map = {
        'jan': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr',
        'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug',
        'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dec': 'Dec'
      };
      
      if (parts.length === 3) {
        const month1 = month_map[parts[0]] || parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
        const month2 = month_map[parts[1]] || parts[1].charAt(0).toUpperCase() + parts[1].slice(1);
        const year = parts[2];
        return `${month1} ${year} - ${month2} ${year}`;
      } else if (parts.length === 2) {
        const month = month_map[parts[0]] || parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
        const year = parts[1];
        return `${month} ${year}`;
      } else {
        return month_str;
      }
    } catch (e) {
      return month_str;
    }
  }
  
  const formatted_month_range = format_month_range(monthRange);
  
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const rowId = row.dataset.rowId;
    const savedEntryId = row.dataset.savedEntryId; // Check if already saved
    
    const date = row.querySelector(`input[name="date_${rowId}"]`)?.value;
    const client = row.querySelector(`input[name="client_${rowId}"]`)?.value.trim();
    const projectId = row.querySelector(`input[name="projectid_${rowId}"]`)?.value.trim();
    const projectName = row.querySelector(`input[name="projectname_${rowId}"]`)?.value.trim();
    const projectType = row.querySelector(`select[name="projecttype_${rowId}"]`)?.value;
    const locationFrom = row.querySelector(`input[name="locationfrom_${rowId}"]`)?.value.trim();
    const locationTo = row.querySelector(`input[name="locationto_${rowId}"]`)?.value.trim();
    const travelMode = row.querySelector(`select[name="travelmode_${rowId}"]`)?.value;
    const amount = row.querySelector(`input[name="amount_${rowId}"]`)?.value;
    const remarks = row.querySelector(`input[name="remarks_${rowId}"]`)?.value.trim();
    const pdfInput = row.querySelector(`input[name="ticketpdf_${rowId}"]`);
    const pdfFile = pdfInput?.files[0];
    
    // Validations
    if (!date || !client || !projectId || !projectName || !projectType || 
        !locationFrom || !locationTo || !travelMode || !amount || parseFloat(amount) <= 0) {
      errors.push(`Row ${i + 1}: Please fill all required fields`);
      errorCount++;
      continue;
    }
    
    if (!isDateInMonthRange(date, monthRange)) {
      const range = monthRanges[monthRange];
      errors.push(`Row ${i + 1}: Date ${date} is outside valid range`);
      errorCount++;
      continue;
    }
    
    if (pdfFile && pdfFile.type !== 'application/pdf') {
      errors.push(`Row ${i + 1}: Only PDF files allowed`);
      errorCount++;
      continue;
    }
    
    try {
      // ✅ CHECK: If entry already saved, UPDATE it instead of creating new
      if (savedEntryId) {
        console.log(`✏️ Updating existing entry: ${savedEntryId}`);
        
        // Prepare update data (JSON for update)
        const updateData = {
          date: date,
          client: client,
          project_id: projectId,
          project_name: projectName,
          project_type: projectType,
          location_from: locationFrom,
          location_to: locationTo,
          travel_mode: travelMode,
          amount: parseFloat(amount),
          remarks: remarks || 'NA',
          month_range: formatted_month_range
        };
        
        const response = await fetch(`${API_URL}/api/ope/update-temp/${savedEntryId}`, {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(updateData)
        });
        
        if (response.ok) {
          console.log(`✅ Entry ${i + 1} updated successfully`);
          successCount++;
          row.style.backgroundColor = '#fef3c7'; // Light yellow for updated
        } else {
          const errorData = await response.json();
          errors.push(`Entry ${i + 1}: ${errorData.detail || 'Update failed'}`);
          errorCount++;
        }
        
      } else {
        // ✅ NEW ENTRY: Create new entry
        console.log(`💾 Saving NEW entry ${i + 1}`);
        
        const formData = new FormData();
        formData.append('date', date);
        formData.append('client', client);
        formData.append('project_id', projectId);
        formData.append('project_name', projectName);
        formData.append('project_type', projectType);
        formData.append('location_from', locationFrom);
        formData.append('location_to', locationTo);
        formData.append('travel_mode', travelMode);
        formData.append('amount', parseFloat(amount));
        formData.append('remarks', remarks || 'NA');
        formData.append('month_range', monthRange);
        
        if (pdfFile) {
          formData.append('ticket_pdf', pdfFile);
        }
        
        const response = await fetch(`${API_URL}/api/ope/save-temp`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`
          },
          body: formData
        });
        
        if (response.ok) {
          const result = await response.json();
          console.log(`✅ Entry ${i + 1} saved successfully`);
          successCount++;
          
          // ✅ Store entry ID in row
          row.dataset.savedEntryId = result.entry_id;
          row.style.backgroundColor = '#f0fdf4'; // Light green
          
        } else {
          const errorData = await response.json();
          errors.push(`Entry ${i + 1}: ${errorData.detail || 'Save failed'}`);
          errorCount++;
        }
      }
      
    } catch (err) {
      errors.push(`Entry ${i + 1}: ${err.message || 'Network error'}`);
      errorCount++;
    }
  }
  
  // Re-enable save button
  if (saveBtn) {
    saveBtn.disabled = false;
    saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Entry';
  }
  
  // Show result
  if (errorCount === 0) {
    showSuccessPopup(`All ${successCount} ${successCount === 1 ? 'entry' : 'entries'} saved successfully!`);
  } else if (successCount > 0) {
    showErrorPopup(`${successCount} entries saved, ${errorCount} failed.<br><br>${errors.join('<br>')}`);
  } else {
    showErrorPopup(`All saves failed:<br><br>${errors.join('<br>')}`);
  }
}

// ===========================================
// SUBMIT ALL ENTRIES - UPDATED VERSION
// ============================================
async function submitAllEntries() {
  const token = localStorage.getItem('access_token');
  const empCode = localStorage.getItem('employee_code');
  
  if (!token || !empCode) {
    showErrorPopup('Authentication required. Please login again.');
    window.location.href = 'login.html';
    return;
  }
  
  const monthRangeSelect = document.getElementById('monthRange');
  const monthRange = monthRangeSelect ? monthRangeSelect.value : '';
  
  if (!monthRange) {
    showErrorPopup('Please select month range first!');
    return;
  }
  
  // ✅ Check if any rows have saved entries
  const tbody = document.getElementById('entryTableBody');
  const rows = tbody.querySelectorAll('tr');
  
  let hasSavedEntries = false;
  for (const row of rows) {
    if (row.dataset.savedEntryId) {
      hasSavedEntries = true;
      break;
    }
  }
  
  if (!hasSavedEntries) {
    showErrorPopup('Please save your entries first using "Save Entry" button before submitting!');
    return;
  }
  
  // Confirmation
  const confirmSubmit = await showConfirmPopup(
    'Submit Confirmation',
    'Are you sure you want to submit? After submission, you cannot edit or delete these entries.',
    'Yes, Submit',
    'Cancel'
  );
  
  if (!confirmSubmit) {
    return;
  }
  
  const submitBtn = document.querySelector('.btn-submit');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
  }
  
  try {
    console.log(`🚀 Submitting all temporary entries to OPE_data...`);
    
    const response = await fetch(`${API_URL}/api/ope/submit-final`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        month_range: monthRange
      })
    });
    
    if (response.ok) {
      const result = await response.json();
      showSuccessPopup(`All entries submitted successfully! Total: ${result.submitted_count}`);
      
      // ✅ NOW clear the form
      tbody.innerHTML = '';
      entryCounter = 0;
      addNewEntryRow();
      
    } else {
      const errorData = await response.json();
      showErrorPopup(errorData.detail || 'Submission failed');
    }
    
  } catch (err) {
    console.error(`❌ Submit error:`, err);
    showErrorPopup(`Network error: ${err.message}`);
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Submit All Entries';
    }
  }
}

// ============================================
// LOAD SAVED ENTRIES ON PAGE LOAD - UPDATED
// ============================================
async function loadSavedEntries() {
  const token = localStorage.getItem('access_token');
  const empCode = localStorage.getItem('employee_code');
  const monthRangeSelect = document.getElementById('monthRange');
  const monthRange = monthRangeSelect ? monthRangeSelect.value : '';
  
  console.log("🔍 loadSavedEntries called");
  console.log("📅 Selected month range:", monthRange);
  
  if (!token || !empCode) {
    console.log("❌ No token or empCode");
    return;
  }
  
  if (!monthRange) {
    console.log("❌ No month range selected");
    return;
  }
  
  try {
    console.log("📥 Loading saved entries from Temp_OPE_data...");
    
    const response = await fetch(`${API_URL}/api/ope/temp-history/${empCode}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (!response.ok) {
      console.log("No saved entries found");
      return;
    }
    
    const data = await response.json();
    console.log("📦 Temp history response:", data);
    
    const savedEntries = data.history || [];
    console.log("📊 Total saved entries:", savedEntries.length);
    
    // ✅ Format month_range for comparison
    function format_month_range(month_str) {
      try {
        const parts = month_str.toLowerCase().split('-');
        const month_map = {
          'jan': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr',
          'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug',
          'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dec': 'Dec'
        };
        
        if (parts.length === 3) {
          const month1 = month_map[parts[0]] || parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
          const month2 = month_map[parts[1]] || parts[1].charAt(0).toUpperCase() + parts[1].slice(1);
          const year = parts[2];
          return `${month1} ${year} - ${month2} ${year}`;
        } else if (parts.length === 2) {
          const month = month_map[parts[0]] || parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
          const year = parts[1];
          return `${month} ${year}`;
        } else {
          return month_str;
        }
      } catch (e) {
        return month_str;
      }
    }
    
    const formatted_month_range = format_month_range(monthRange);
    console.log("📅 Formatted month range:", formatted_month_range);
    
    // ✅ Filter by selected month range (compare both formats)
    const filteredEntries = savedEntries.filter(entry => {
      const entry_month = entry.month_range;
      const formatted_entry_month = format_month_range(entry_month);
      
      console.log(`Comparing: "${entry_month}" or "${formatted_entry_month}" with "${formatted_month_range}"`);
      
      return entry_month === formatted_month_range || 
             formatted_entry_month === formatted_month_range ||
             entry_month === monthRange;
    });
    
    console.log("✅ Filtered entries for this month:", filteredEntries.length);
    
    if (filteredEntries.length === 0) {
      console.log("No saved entries for this month");
      return;
    }
    
    console.log(`✅ Found ${filteredEntries.length} saved entries`);
    
    // ✅ Clear existing rows and populate with saved data
    const tbody = document.getElementById('entryTableBody');
    tbody.innerHTML = '';
    entryCounter = 0;
    
    for (const entry of filteredEntries) {
      entryCounter++;
      
      const row = document.createElement('tr');
      row.dataset.rowId = entryCounter;
      row.dataset.savedEntryId = entry._id; // Store saved ID
      row.style.backgroundColor = '#f0fdf4'; // Light green for saved
      
      row.innerHTML = `
        <td><strong>${entryCounter}</strong></td>
        <td><input type="date" name="date_${entryCounter}" value="${entry.date}" required /></td>
        <td>
          <div class="table-action-btns">
            <button type="button" class="copy-btn" onclick="copyRow(${entryCounter})">
              <i class="fas fa-copy"></i> Copy
            </button>
            <button type="button" class="paste-btn" onclick="pasteRow(${entryCounter})">
              <i class="fas fa-paste"></i> Paste
            </button>
          </div>
        </td>
        <td><input type="text" name="client_${entryCounter}" value="${entry.client}" placeholder="Client Name" required /></td>
        <td><input type="text" name="projectid_${entryCounter}" value="${entry.project_id}" placeholder="Project ID" required /></td>
        <td><input type="text" name="projectname_${entryCounter}" value="${entry.project_name}" placeholder="Project Name" required /></td>
        <td>
          <select name="projecttype_${entryCounter}" required>
            <option value="" disabled>Select Type</option>
            <option value="Concurrent" ${entry.project_type === 'Concurrent' ? 'selected' : ''}>Concurrent</option>
            <option value="KYC" ${entry.project_type === 'KYC' ? 'selected' : ''}>KYC</option>
            <option value="IFC" ${entry.project_type === 'IFC' ? 'selected' : ''}>IFC</option>
            <option value="Statutory" ${entry.project_type === 'Statutory' ? 'selected' : ''}>Statutory</option>
            <option value="Internal" ${entry.project_type === 'Internal' ? 'selected' : ''}>Internal</option>
            <option value="Cyber Security" ${entry.project_type === 'Cyber Security' ? 'selected' : ''}>Cyber Security</option>
            <option value="Consulting" ${entry.project_type === 'Consulting' ? 'selected' : ''}>Consulting</option>
            <option value="Outsourcing" ${entry.project_type === 'Outsourcing' ? 'selected' : ''}>Outsourcing</option>
            <option value="Other" ${entry.project_type === 'Other' ? 'selected' : ''}>Other</option>
          </select>
        </td>
        <td><input type="text" name="locationfrom_${entryCounter}" value="${entry.location_from}" placeholder="From" required /></td>
        <td><input type="text" name="locationto_${entryCounter}" value="${entry.location_to}" placeholder="To" required /></td>
        <td>
          <select name="travelmode_${entryCounter}" required>
            <option value="" disabled>Select Mode</option>
            <option value="metro_recharge" ${entry.travel_mode === 'metro_recharge' ? 'selected' : ''}>Metro Recharge</option>
            <option value="metro_pass" ${entry.travel_mode === 'metro_pass' ? 'selected' : ''}>Metro Pass</option>
            <option value="metro_tickets" ${entry.travel_mode === 'metro_tickets' ? 'selected' : ''}>Metro Tickets</option>
            <option value="shared_auto" ${entry.travel_mode === 'shared_auto' ? 'selected' : ''}>Shared Auto</option>
            <option value="shared_taxi" ${entry.travel_mode === 'shared_taxi' ? 'selected' : ''}>Shared Taxi</option>
            <option value="meter_auto" ${entry.travel_mode === 'meter_auto' ? 'selected' : ''}>Meter Auto</option>
            <option value="taxi_cab" ${entry.travel_mode === 'taxi_cab' ? 'selected' : ''}>Taxi / Cab</option>
            <option value="bus_ticket" ${entry.travel_mode === 'bus_ticket' ? 'selected' : ''}>Bus Tickets</option>
            <option value="bus_pass" ${entry.travel_mode === 'bus_pass' ? 'selected' : ''}>Bus Pass</option>
            <option value="train_pass 1st" ${entry.travel_mode === 'train_pass 1st' ? 'selected' : ''}>Train Pass - 1st Class</option>
            <option value="train_pass 2nd" ${entry.travel_mode === 'train_pass 2nd' ? 'selected' : ''}>Train Pass - 2nd Class</option>
            <option value="train_ticket" ${entry.travel_mode === 'train_ticket' ? 'selected' : ''}>Train Ticket</option>
            <option value="other" ${entry.travel_mode === 'other' ? 'selected' : ''}>Other</option>
          </select>
        </td>
        <td><input type="number" name="amount_${entryCounter}" value="${entry.amount}" placeholder="Amount" min="0" step="0.01" required /></td>
        <td><input type="text" name="remarks_${entryCounter}" value="${entry.remarks || ''}" placeholder="Remarks" /></td>
        <td><input type="file" name="ticketpdf_${entryCounter}" accept=".pdf" /></td>
        <td>
          <button type="button" class="delete-row-btn" onclick="deleteSavedRow(${entryCounter}, '${entry._id}', '${monthRange}')">
            <i class="fas fa-trash"></i> Delete
          </button>
        </td>
      `;
      
      tbody.appendChild(row);
    }
    
    console.log("✅ Loaded saved entries into form");
    
  } catch (error) {
    console.error("❌ Error loading saved entries:", error);
  }
}

// ============================================
// DELETE SAVED ROW - NEW FUNCTION
// ============================================
async function deleteSavedRow(rowId, entryId, monthRange) {
  // ✅ UPDATED: Use custom popup instead of confirm
  const confirmed = await showDeleteConfirmPopup(
    'This action cannot be undone. The entry will be permanently removed from your saved data.'
  );
  
  if (!confirmed) {
    return;
  }
  
  const token = localStorage.getItem('access_token');
  
  // Format month_range
  function format_month_range(month_str) {
    try {
      const parts = month_str.toLowerCase().split('-');
      const month_map = {
        'jan': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr',
        'may': 'May', 'jun': 'Jun', 'jul': 'Jul', 'aug': 'Aug',
        'sep': 'Sep', 'oct': 'Oct', 'nov': 'Nov', 'dec': 'Dec'
      };
      
      if (parts.length === 3) {
        const month1 = month_map[parts[0]] || parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
        const month2 = month_map[parts[1]] || parts[1].charAt(0).toUpperCase() + parts[1].slice(1);
        const year = parts[2];
        return `${month1} ${year} - ${month2} ${year}`;
      } else if (parts.length === 2) {
        const month = month_map[parts[0]] || parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
        const year = parts[1];
        return `${month} ${year}`;
      } else {
        return month_str;
      }
    } catch (e) {
      return month_str;
    }
  }
  
  const formatted_month_range = format_month_range(monthRange);
  
  try {
    console.log(`🗑️ Deleting entry ${entryId} with month: ${formatted_month_range}`);
    
    const response = await fetch(`${API_URL}/api/ope/delete-temp/${entryId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({ month_range: formatted_month_range })
    });
    
    if (response.ok) {
      showSuccessPopup('Entry deleted successfully!');
      
      // Remove row from table
      const row = document.querySelector(`tr[data-row-id="${rowId}"]`);
      if (row) {
        row.remove();
      }
      
      // If no entries left, add blank row
      const tbody = document.getElementById('entryTableBody');
      if (tbody.querySelectorAll('tr').length === 0) {
        addNewEntryRow();
      }
      
    } else {
      const errorData = await response.json();
      showErrorPopup(errorData.detail || 'Delete failed');
    }
    
  } catch (error) {
    console.error('Delete error:', error);
    showErrorPopup('Network error');
  }
}

// ✅ Add this in DOMContentLoaded
document.addEventListener('DOMContentLoaded', function() {
  setupNavigation();
  checkUserRole();

  // ✅ Load saved entries when month range changes
  const monthRangeSelect = document.getElementById('monthRange');
  if (monthRangeSelect) {
    monthRangeSelect.addEventListener('change', async function() {
      const selectedMonth = this.value;
      
      if (selectedMonth) {
        // Load saved entries for this month
        await loadSavedEntries();
      }
    });
  }
});

// ✅ NEW: Confirmation Popup Function
function showConfirmPopup(title, message, confirmText, cancelText) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.6);
      z-index: 99999;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    `;

    const popup = document.createElement('div');
    popup.style.cssText = `
      background: white;
      padding: 30px;
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
      text-align: center;
      max-width: 450px;
      width: 90%;
      animation: slideUp 0.3s ease;
    `;

    popup.innerHTML = `
      <div style="
        width: 70px;
        height: 70px;
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 18px;
      ">
        <i class="fas fa-exclamation-triangle" style="font-size: 32px; color: white;"></i>
      </div>
      <h2 style="font-size: 21px; color: #1f2937; margin-bottom: 10px; font-weight: 600;">${title}</h2>
      <p style="color: #6b7280; margin-bottom: 25px; font-size: 14.5px; line-height: 1.5;">${message}</p>
      <div style="display: flex; gap: 12px; justify-content: center;">
        <button id="confirmBtn" style="
          padding: 12px 24px;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          color: white;
          border: none;
          border-radius: 10px;
          font-size: 15px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.3s ease;
          box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);
        ">${confirmText}</button>
        <button id="cancelBtn" style="
          padding: 12px 24px;
          background: #f1f5f9;
          color: #4a5568;
          border: 2px solid #e2e8f0;
          border-radius: 10px;
          font-size: 15px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.3s ease;
        ">${cancelText}</button>
      </div>
    `;

    overlay.appendChild(popup);
    document.body.appendChild(overlay);

    document.getElementById('confirmBtn').addEventListener('click', () => {
      document.body.removeChild(overlay);
      resolve(true);
    });

    document.getElementById('cancelBtn').addEventListener('click', () => {
      document.body.removeChild(overlay);
      resolve(false);
    });

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        document.body.removeChild(overlay);
        resolve(false);
      }
    });
  });
}

// Add this in your <style> section or style.css
const pulseAnimation = `
@keyframes pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(102, 126, 234, 0.7);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(102, 126, 234, 0);
  }
}
`;

// Add to existing style element
const existingStyle = document.querySelector('style');
if (existingStyle) {
    existingStyle.textContent += pulseAnimation;
}

// PENDING SECTION
let allPendingEmployees = [];

async function loadPendingData(token, empCode) {
    try {
        document.getElementById('pendingLoadingDiv').style.display = 'block';
        document.getElementById('pendingTableSection').style.display = 'none';
        document.getElementById('pendingNoDataDiv').style.display = 'none';

        const response = await fetch(`${API_URL}/api/ope/manager/pending`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) throw new Error('Failed to fetch pending entries');

        const data = await response.json();
        allPendingEmployees = data.employees || [];

        console.log("✅ Pending employees:", allPendingEmployees);
        
        if (allPendingEmployees.length === 0) {
            showPendingNoData();
        } else {
            displayPendingEmployeeTable(allPendingEmployees);
        }
    } catch (error) {
        console.error('❌ Error:', error);
        document.getElementById('pendingLoadingDiv').style.display = 'none';
        showPendingNoData();
    }
}

function populatePendingMonthFilter() {
    const monthSet = new Set();
    allPendingData.forEach(item => {
        if (item.month_range) monthSet.add(item.month_range);
    });

    const select = document.getElementById('pendingMonthFilter');
    select.innerHTML = '<option value="">All Months</option>';

    Array.from(monthSet).sort().forEach(month => {
        const option = document.createElement('option');
        option.value = month;
        option.textContent = month;
        select.appendChild(option);
    });

    select.addEventListener('change', function() {
        const selectedMonth = this.value;
        if (selectedMonth === '') {
            displayPendingTable(allPendingData);
        } else {
            const filteredData = allPendingData.filter(item => item.month_range === selectedMonth);
            displayPendingTable(filteredData);
        }
    });
}

function displayPendingEmployeeTable(employees) {
    const tbody = document.getElementById('pendingTableBody');
    if (!tbody) return;

    tbody.innerHTML = '';

    if (!employees || employees.length === 0) {
        showPendingNoData();
        return;
    }

    employees.forEach((employee) => {
        const row = document.createElement('tr');
        row.style.cssText = 'transition: background-color 0.2s ease;';
        
        // Add hover effect
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f8fafc';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
        
        row.innerHTML = `
            <td style="text-align: center; font-weight: 600; color: #475569;">
                ${employee.employeeId}
            </td>
            <td style="text-align: left;">
                <a href="#" onclick="showEmployeeModal('${employee.employeeId}'); return false;" 
                   style="color: #3b82f6; text-decoration: none; font-weight: 600; font-size: 15px; display: flex; align-items: center; gap: 8px;">
                    <i class="fas fa-user-circle" style="font-size: 18px;"></i>
                    ${employee.employeeName}
                </a>
            </td>
            <td style="text-align: center;">
                <span style="
                    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); 
                    color: white; 
                    padding: 8px 16px; 
                    border-radius: 20px; 
                    font-size: 13px; 
                    font-weight: 600;
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    box-shadow: 0 2px 8px rgba(245, 158, 11, 0.3);
                ">
                    <i class="fas fa-clock"></i> 
                    ${employee.pendingCount} Pending
                </span>
            </td>
            <td style="text-align: center;">
                <div style="display: flex; gap: 10px; justify-content: center; align-items: center;">
                    <button onclick="approveEmployee('${employee.employeeId}')" 
                            style="
                                padding: 10px 20px; 
                                background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                                color: white; 
                                border: none; 
                                border-radius: 8px; 
                                cursor: pointer; 
                                font-weight: 600; 
                                font-size: 14px;
                                display: inline-flex; 
                                align-items: center; 
                                gap: 6px;
                                transition: all 0.3s ease;
                                box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
                            "
                            onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(16, 185, 129, 0.4)';"
                            onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(16, 185, 129, 0.3)';">
                        <i class="fas fa-check-circle"></i> Approve
                    </button>
                    <button onclick="rejectEmployee('${employee.employeeId}')" 
                            style="
                                padding: 10px 20px; 
                                background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); 
                                color: white; 
                                border: none; 
                                border-radius: 8px; 
                                cursor: pointer; 
                                font-weight: 600; 
                                font-size: 14px;
                                display: inline-flex; 
                                align-items: center; 
                                gap: 6px;
                                transition: all 0.3s ease;
                                box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
                            "
                            onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(239, 68, 68, 0.4)';"
                            onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(239, 68, 68, 0.3)';">
                        <i class="fas fa-times-circle"></i> Reject
                    </button>
                </div>
            </td>
        `;
        
        tbody.appendChild(row);
    });

    document.getElementById('pendingLoadingDiv').style.display = 'none';
    document.getElementById('pendingTableSection').style.display = 'block';
}

function showPendingNoData() {
    document.getElementById('pendingLoadingDiv').style.display = 'none';
    document.getElementById('pendingTableSection').style.display = 'none';
    document.getElementById('pendingNoDataDiv').style.display = 'block';
}

// APPROVE SECTION
let allApproveData = [];

async function loadApproveData(token, empCode) {
    try {
        console.log("🔍 Loading approve data for manager:", empCode);
        
        document.getElementById('approveLoadingDiv').style.display = 'block';
        document.getElementById('approveTableSection').style.display = 'none';
        document.getElementById('approveNoDataDiv').style.display = 'none';

        // ✅ Get list of approved employees under this manager
        const approvedListResponse = await fetch(`${API_URL}/api/ope/manager/approved-list`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!approvedListResponse.ok) {
            const errorText = await approvedListResponse.text();
            console.error("❌ Failed to fetch approved list:", errorText);
            throw new Error('Failed to fetch approved list');
        }

        const approvedListData = await approvedListResponse.json();
        const approvedEmployeeCodes = approvedListData.employee_codes || [];

        console.log("✅ Approved employee codes:", approvedEmployeeCodes);
        console.log("📊 Total approved employees:", approvedEmployeeCodes.length);

        if (approvedEmployeeCodes.length === 0) {
            console.log("📭 No approved employees found");
            showApproveNoData();
            return;
        }

        // ✅ Fetch approved entries for each employee
        allApproveData = [];

        for (const empCode of approvedEmployeeCodes) {
            console.log(`📥 Fetching approved data for employee: ${empCode}`);
            
            const response = await fetch(`${API_URL}/api/ope/approved/${empCode}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                const data = await response.json();
                console.log(`✅ Got ${data.approved?.length || 0} approved entries for ${empCode}`);
                allApproveData = allApproveData.concat(data.approved || []);
            } else {
                const errorText = await response.text();
                console.error(`❌ Failed to fetch for ${empCode}:`, errorText);
            }
        }

        console.log("✅ Total approved entries loaded:", allApproveData.length);

        populateApproveMonthFilter();
        
        if (allApproveData.length === 0) {
            console.log("📭 No approved entries found");
            showApproveNoData();
        } else {
            console.log("🎨 Displaying approved table");
            displayApproveTable(allApproveData);
        }
    } catch (error) {
        console.error('❌ Error in loadApproveData:', error);
        document.getElementById('approveLoadingDiv').style.display = 'none';
        showApproveNoData();
    }
}

function populateApproveMonthFilter() {
    const monthSet = new Set();
    allApproveData.forEach(item => {
        if (item.month_range) monthSet.add(item.month_range);
    });

    const select = document.getElementById('approveMonthFilter');
    select.innerHTML = '<option value="">All Months</option>';

    Array.from(monthSet).sort().forEach(month => {
        const option = document.createElement('option');
        option.value = month;
        option.textContent = month;
        select.appendChild(option);
    });

    select.addEventListener('change', function() {
        const selectedMonth = this.value;
        if (selectedMonth === '') {
            displayApproveTable(allApproveData);
        } else {
            const filteredData = allApproveData.filter(item => item.month_range === selectedMonth);
            displayApproveTable(filteredData);
        }
    });
}

function displayApproveTable(data) {
    console.log("🎨 displayApproveTable called with data:", data);
    console.log("📊 Data length:", data?.length || 0);
    
    const tbody = document.getElementById('approveTableBody');
    if (!tbody) {
        console.error("❌ approveTableBody not found!");
        return;
    }

    tbody.innerHTML = '';

    if (!data || data.length === 0) {
        showApproveNoData();
        return;
    }

    // ✅ Remove duplicates based on _id
    const uniqueData = [];
    const seenIds = new Set();
    
    data.forEach(entry => {
        if (!seenIds.has(entry._id)) {
            seenIds.add(entry._id);
            uniqueData.push(entry);
        }
    });
    
    console.log(`✅ Removed duplicates: ${data.length} → ${uniqueData.length}`);

    // ✅ Sort by date (newest first)
    uniqueData.sort((a, b) => {
        const dateA = new Date(a.date || '1970-01-01');
        const dateB = new Date(b.date || '1970-01-01');
        return dateB - dateA;
    });

    uniqueData.forEach((entry) => {
        const row = document.createElement('tr');
        row.style.cssText = 'transition: background-color 0.2s ease;';
        
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f0fdf4';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
        
        row.innerHTML = `
            <td style="font-weight: 500;">${entry.date || '-'}</td>
            <td>
                <span style="
                    background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                    color: white; 
                    padding: 6px 12px; 
                    border-radius: 6px; 
                    font-size: 12px; 
                    font-weight: 600;
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                ">
                    <i class="fas fa-check-circle"></i> APPROVED
                </span>
            </td>
            <td>${entry.client || '-'}</td>
            <td style="font-weight: 600; color: #3b82f6;">${entry.project_id || '-'}</td>
            <td>${entry.project_name || '-'}</td>
            <td><span style="background: #e0e7ff; color: #4338ca; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 600;">${entry.project_type || '-'}</span></td>
            <td>${entry.location_from || '-'}</td>
            <td>${entry.location_to || '-'}</td>
            <td>${getTravelModeLabel(entry.travel_mode)}</td>
            <td style="font-weight: 700; color: #059669; font-size: 15px;">₹${entry.amount || 0}</td>
            <td style="max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${entry.remarks || 'NA'}">${entry.remarks || 'NA'}</td>
            <td style="text-align: center;">
                ${entry.ticket_pdf 
                    ? `<button class="view-pdf-btn" onclick="viewPdf('${entry._id}', false)" style="
                        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                        color: white;
                        border: none;
                        padding: 6px 12px;
                        border-radius: 6px;
                        cursor: pointer;
                        font-size: 13px;
                        font-weight: 600;
                        display: inline-flex;
                        align-items: center;
                        gap: 6px;
                        transition: all 0.2s ease;
                      "
                      onmouseover="this.style.transform='translateY(-2px)'"
                      onmouseout="this.style.transform='translateY(0)'">
                        <i class="fas fa-file-pdf"></i> View
                      </button>` 
                    : '<span style="color: #9ca3af; font-size: 13px;">No PDF</span>'}
            </td>
            <td style="color: #059669; font-weight: 600;">${entry.approved_by || '-'}</td>
            <td style="color: #6b7280; font-size: 13px;">${entry.approved_date ? new Date(entry.approved_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '-'}</td>
            <td style="text-align: center;">
                <button onclick="rejectApprovedEntry('${entry._id}', '${entry.employee_id || ''}')" style="
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 8px;
                    cursor: pointer;
                    font-weight: 600;
                    font-size: 14px;
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    transition: all 0.3s ease;
                    box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
                "
                onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(239, 68, 68, 0.4)';"
                onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(239, 68, 68, 0.3)';">
                    <i class="fas fa-times-circle"></i> Reject
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });

    document.getElementById('approveLoadingDiv').style.display = 'none';
    document.getElementById('approveTableSection').style.display = 'block';
    
    console.log(`✅ Displayed ${uniqueData.length} unique approved entries`);
}

function showApproveNoData() {
    document.getElementById('approveLoadingDiv').style.display = 'none';
    document.getElementById('approveTableSection').style.display = 'none';
    document.getElementById('approveNoDataDiv').style.display = 'block';
}

// REJECT SECTION
let allRejectData = [];

async function loadRejectData(token, empCode) {
    try {
        console.log("🔍 Loading reject data for manager:", empCode);
        
        document.getElementById('rejectLoadingDiv').style.display = 'block';
        document.getElementById('rejectTableSection').style.display = 'none';
        document.getElementById('rejectNoDataDiv').style.display = 'none';

        // ✅ Get list of rejected employees under this manager
        const rejectedListResponse = await fetch(`${API_URL}/api/ope/manager/rejected-list`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!rejectedListResponse.ok) {
            const errorText = await rejectedListResponse.text();
            console.error("❌ Failed to fetch rejected list:", errorText);
            throw new Error('Failed to fetch rejected list');
        }

        const rejectedListData = await rejectedListResponse.json();
        const rejectedEmployeeCodes = rejectedListData.employee_codes || [];

        console.log("✅ Rejected employee codes:", rejectedEmployeeCodes);
        console.log("📊 Total rejected employees:", rejectedEmployeeCodes.length);

        if (rejectedEmployeeCodes.length === 0) {
            console.log("📭 No rejected employees found");
            showRejectNoData();
            return;
        }

        // ✅ Fetch rejected entries for each employee
        allRejectData = [];

        for (const empCode of rejectedEmployeeCodes) {
            console.log(`📥 Fetching rejected data for employee: ${empCode}`);
            
            const response = await fetch(`${API_URL}/api/ope/rejected/${empCode}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (response.ok) {
                const data = await response.json();
                console.log(`✅ Got ${data.rejected?.length || 0} rejected entries for ${empCode}`);
                allRejectData = allRejectData.concat(data.rejected || []);
            } else {
                const errorText = await response.text();
                console.error(`❌ Failed to fetch for ${empCode}:`, errorText);
            }
        }

        console.log("✅ Total rejected entries loaded:", allRejectData.length);

        populateRejectMonthFilter();
        
        if (allRejectData.length === 0) {
            console.log("📭 No rejected entries found");
            showRejectNoData();
        } else {
            console.log("🎨 Displaying reject table");
            displayRejectTable(allRejectData);
        }
    } catch (error) {
        console.error('❌ Error in loadRejectData:', error);
        document.getElementById('rejectLoadingDiv').style.display = 'none';
        showRejectNoData();
    }
}

function populateRejectMonthFilter() {
    const monthSet = new Set();
    allRejectData.forEach(item => {
        if (item.month_range) monthSet.add(item.month_range);
    });

    const select = document.getElementById('rejectMonthFilter');
    select.innerHTML = '<option value="">All Months</option>';

    Array.from(monthSet).sort().forEach(month => {
        const option = document.createElement('option');
        option.value = month;
        option.textContent = month;
        select.appendChild(option);
    });

    select.addEventListener('change', function() {
        const selectedMonth = this.value;
        if (selectedMonth === '') {
            displayRejectTable(allRejectData);
        } else {
            const filteredData = allRejectData.filter(item => item.month_range === selectedMonth);
            displayRejectTable(filteredData);
        }
    });
}

function displayRejectTable(data) {
    console.log("🎨 displayRejectTable called with data:", data);
    console.log("📊 Data length:", data?.length || 0);
    
    const tbody = document.getElementById('rejectTableBody');
    if (!tbody) {
        console.error("❌ rejectTableBody not found!");
        return;
    }

    tbody.innerHTML = '';

    if (!data || data.length === 0) {
        showRejectNoData();
        return;
    }

    // ✅ Remove duplicates based on _id
    const uniqueData = [];
    const seenIds = new Set();
    
    data.forEach(entry => {
        if (!seenIds.has(entry._id)) {
            seenIds.add(entry._id);
            uniqueData.push(entry);
        }
    });
    
    console.log(`✅ Removed duplicates: ${data.length} → ${uniqueData.length}`);

    // ✅ Sort by date (newest first)
    uniqueData.sort((a, b) => {
        const dateA = new Date(a.date || '1970-01-01');
        const dateB = new Date(b.date || '1970-01-01');
        return dateB - dateA;
    });

    uniqueData.forEach((entry) => {
        const row = document.createElement('tr');
        row.style.cssText = 'transition: background-color 0.2s ease;';
        
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#fef2f2';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
        
        row.innerHTML = `
            <td style="font-weight: 500;">${entry.date || '-'}</td>
            <td>
                <span style="
                    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); 
                    color: white; 
                    padding: 6px 12px; 
                    border-radius: 6px; 
                    font-size: 12px; 
                    font-weight: 600;
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                ">
                    <i class="fas fa-times-circle"></i> REJECTED
                </span>
            </td>
            <td>${entry.client || '-'}</td>
            <td style="font-weight: 600; color: #3b82f6;">${entry.project_id || '-'}</td>
            <td>${entry.project_name || '-'}</td>
            <td><span style="background: #fee2e2; color: #991b1b; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 600;">${entry.project_type || '-'}</span></td>
            <td>${entry.location_from || '-'}</td>
            <td>${entry.location_to || '-'}</td>
            <td>${getTravelModeLabel(entry.travel_mode)}</td>
            <td style="font-weight: 700; color: #dc2626; font-size: 15px;">₹${entry.amount || 0}</td>
            <td style="max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${entry.remarks || 'NA'}">${entry.remarks || 'NA'}</td>
            <td style="text-align: center;">
                ${entry.ticket_pdf 
                    ? `<button class="view-pdf-btn" onclick="viewPdf('${entry._id}', false)" style="
                        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                        color: white;
                        border: none;
                        padding: 6px 12px;
                        border-radius: 6px;
                        cursor: pointer;
                        font-size: 13px;
                        font-weight: 600;
                        display: inline-flex;
                        align-items: center;
                        gap: 6px;
                        transition: all 0.2s ease;
                      "
                      onmouseover="this.style.transform='translateY(-2px)'"
                      onmouseout="this.style.transform='translateY(0)'">
                        <i class="fas fa-file-pdf"></i> View
                      </button>` 
                    : '<span style="color: #9ca3af; font-size: 13px;">No PDF</span>'}
            </td>
            <td style="color: #dc2626; font-weight: 600;">${entry.rejected_by || '-'}</td>
            <td style="color: #6b7280; font-size: 13px;">${entry.rejected_date ? new Date(entry.rejected_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '-'}</td>
            <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #dc2626; font-weight: 500;" title="${entry.rejection_reason || '-'}">
                ${entry.rejection_reason || '-'}
            </td>
            <td style="text-align: center;">
                <button onclick="approveRejectedEntry('${entry._id}', '${entry.employee_id || ''}')" style="
                    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 8px;
                    cursor: pointer;
                    font-weight: 600;
                    font-size: 14px;
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    transition: all 0.3s ease;
                    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
                "
                onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(16, 185, 129, 0.4)';"
                onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(16, 185, 129, 0.3)';">
                    <i class="fas fa-check-circle"></i> Approve
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });

    document.getElementById('rejectLoadingDiv').style.display = 'none';
    document.getElementById('rejectTableSection').style.display = 'block';
    
    console.log(`✅ Displayed ${uniqueData.length} unique rejected entries`);
}

// ✅ NEW: Reject an approved entry
async function rejectApprovedEntry(entryId, employeeId) {
  const token = localStorage.getItem('access_token');
  
  try {
    console.log("❌ Rejecting approved entry:", entryId);
    
    // Ask for rejection reason
    const reason = await showRejectReasonPopup();
    
    if (!reason) {
      return; // User cancelled
    }
    
    const response = await fetch(`${API_URL}/api/ope/manager/reject-single`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ 
        entry_id: entryId,
        employee_id: employeeId,
        reason: reason 
      })
    });
    
    if (response.ok) {
      showSuccessPopup('Entry rejected successfully!');
      
      // Reload approve data
      const empCode = localStorage.getItem('employee_code');
      await loadApproveData(token, empCode);
      
    } else {
      const errorData = await response.json();
      showErrorPopup(errorData.detail || 'Rejection failed');
    }
    
  } catch (error) {
    console.error('Rejection error:', error);
    showErrorPopup('Network error during rejection');
  }
}

// ✅ NEW: Approve a rejected entry
async function approveRejectedEntry(entryId, employeeId) {
  const token = localStorage.getItem('access_token');
  
  try {
    console.log("✅ Approving rejected entry:", entryId);
    
    const confirmed = await showConfirmPopup(
      'Approve Entry',
      'Are you sure you want to approve this previously rejected entry?',
      'Yes, Approve',
      'Cancel'
    );
    
    if (!confirmed) {
      return;
    }
    
    const response = await fetch(`${API_URL}/api/ope/manager/approve-single`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ 
        entry_id: entryId,
        employee_id: employeeId
      })
    });
    
    if (response.ok) {
      showSuccessPopup('Entry approved successfully!');
      
      // Reload reject data
      const empCode = localStorage.getItem('employee_code');
      await loadRejectData(token, empCode);
      
    } else {
      const errorData = await response.json();
      showErrorPopup(errorData.detail || 'Approval failed');
    }
    
  } catch (error) {
    console.error('Approval error:', error);
    showErrorPopup('Network error during approval');
  }
}

function showRejectNoData() {
    document.getElementById('rejectLoadingDiv').style.display = 'none';
    document.getElementById('rejectTableSection').style.display = 'none';
    document.getElementById('rejectNoDataDiv').style.display = 'block';
}

// Check if user is a reporting manager

async function checkUserRole() {
  try {
    const token = localStorage.getItem("access_token");
    const empCode = localStorage.getItem("employee_code");
    
    if (!token || !empCode) {
      console.log("❌ No token or empCode, skipping role check");
      return false;
    }
    
    console.log("🔍 Checking user role for:", empCode);
    
    const response = await fetch(`${API_URL}/api/check-manager/${empCode}`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
    
    if (!response.ok) {
      console.error("❌ Role check failed:", response.status);
      return false;
    }
    
    const data = await response.json();
    console.log("✅ Role check result:", data);
    
    // Store role in localStorage
    localStorage.setItem("is_manager", data.isManager);
    
    // Show/hide manager-only buttons
    toggleManagerButtons(data.isManager);
    
    return data.isManager;
    
  } catch (error) {
    console.error("❌ Error checking role:", error);
    return false;
  }
}

// Toggle visibility of manager-only sidebar buttons
function toggleManagerButtons(isManager) {
  const navPending = document.getElementById('navPending');
  const navApprove = document.getElementById('navApprove');
  const navReject = document.getElementById('navReject');
  
  console.log("🔧 toggleManagerButtons called with isManager:", isManager);
  
  if (isManager) {
    console.log("👔 User is a manager - showing buttons");
    if (navPending) {
      navPending.style.display = 'flex';
      console.log("✅ Pending button shown");
    }
    if (navApprove) {
      navApprove.style.display = 'flex';
      console.log("✅ Approve button shown");
    }
    if (navReject) {
      navReject.style.display = 'flex';
      console.log("✅ Reject button shown");
    }
  } else {
    console.log("👤 User is an employee - hiding buttons");
    if (navPending) navPending.style.display = 'none';
    if (navApprove) navApprove.style.display = 'none';
    if (navReject) navReject.style.display = 'none';
  }
}

// Update checkUserRole to use isManager
async function checkUserRole() {
  try {
    const token = localStorage.getItem("access_token");
    const empCode = localStorage.getItem("employee_code");
    
    console.log("🔍 Checking user role...");
    
    const response = await fetch(`${API_URL}/api/check-manager/${empCode}`, {
      headers: {
        Authorization: `Bearer ${token}`
      }
    });
    
    if (!response.ok) {
      console.error("❌ Role check failed");
      return false;
    }
    
    const data = await response.json();
    console.log("✅ Role check result:", data);
    
    // Store role in localStorage using isManager
    localStorage.setItem("is_manager", data.isManager);
    
    // Show/hide manager-only buttons
    toggleManagerButtons(data.isManager);
    
    return data.isManager;
    
  } catch (error) {
    console.error("❌ Error checking role:", error);
    return false;
  }
}

function showEmployeeModal(employeeId) {
    const employee = allPendingEmployees.find(e => e.employeeId === employeeId);
    if (!employee) return;

    // Create modal overlay
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.7);
        z-index: 99999;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 20px;
    `;

    const modal = document.createElement('div');
    modal.style.cssText = `
        background: white;
        border-radius: 16px;
        max-width: 1200px;
        width: 95%;
        max-height: 90vh;
        overflow-y: auto;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    `;

    // Build entries table
    let entriesHtml = employee.entries.map(entry => `
        <tr>
            <td>${entry.date}</td>
            <td>${entry.client}</td>
            <td>${entry.project_id}</td>
            <td>${entry.project_name}</td>
            <td>${entry.project_type}</td>
            <td>${entry.location_from}</td>
            <td>${entry.location_to}</td>
            <td>${getTravelModeLabel(entry.travel_mode)}</td>
            <td>₹${entry.amount}</td>
            <td>${entry.remarks || 'NA'}</td>
        </tr>
    `).join('');

    modal.innerHTML = `
        <div style="padding: 30px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
                <div>
                    <h2 style="font-size: 24px; color: #1e293b; margin-bottom: 5px;">
                        ${employee.employeeName}
                    </h2>
                    <p style="color: #64748b; font-size: 14px;">
                        ${employee.employeeId} | ${employee.designation}
                    </p>
                </div>
                <button onclick="this.closest('.modal-overlay').remove()" 
                        style="background: #ef4444; color: white; border: none; padding: 10px 20px; 
                               border-radius: 8px; cursor: pointer; font-weight: 600;">
                    <i class="fas fa-times"></i> Close
                </button>
            </div>

            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead style="background: #f1f5f9;">
                        <tr>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">Date</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">Client</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">Project ID</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">Project Name</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">Type</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">From</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">To</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">Travel Mode</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">Amount</th>
                            <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">Remarks</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${entriesHtml}
                    </tbody>
                </table>
            </div>

            <div style="margin-top: 25px; display: flex; gap: 15px; justify-content: flex-end;">
                <button onclick="approveEmployee('${employee.employeeId}')" 
                        style="padding: 12px 24px; background: #10b981; color: white; border: none; 
                               border-radius: 10px; cursor: pointer; font-weight: 600; font-size: 15px;">
                    <i class="fas fa-check"></i> Approve All
                </button>
                <button onclick="rejectEmployee('${employee.employeeId}')" 
                        style="padding: 12px 24px; background: #ef4444; color: white; border: none; 
                               border-radius: 10px; cursor: pointer; font-weight: 600; font-size: 15px;">
                    <i class="fas fa-times"></i> Reject All
                </button>
            </div>
        </div>
    `;

    overlay.className = 'modal-overlay';
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Close on overlay click
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            overlay.remove();
        }
    });
}

async function approveEmployee(employeeId) {
  const token = localStorage.getItem('access_token');
  
  try {
    console.log("✅ Approving employee:", employeeId);
    
    const response = await fetch(`${API_URL}/api/ope/manager/approve/${employeeId}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (response.ok) {
      const result = await response.json();
      showSuccessPopup(`Approved ${result.approved_count} entries for employee ${employeeId}`);
      
      // Close modal if open
      const modals = document.querySelectorAll('.modal-overlay');
      modals.forEach(modal => modal.remove());
      
      // Reload pending data
      const empCode = localStorage.getItem('employee_code');
      await loadPendingData(token, empCode);
      
    } else {
      const errorData = await response.json();
      showErrorPopup(errorData.detail || 'Approval failed');
    }
    
  } catch (error) {
    console.error('Approval error:', error);
    showErrorPopup('Network error during approval');
  }
}

async function rejectEmployee(employeeId) {
  const token = localStorage.getItem('access_token');
  
  try {
    console.log("❌ Rejecting employee:", employeeId);
    
    // ✅ Ask for rejection reason
    const reason = await showRejectReasonPopup();
    
    if (!reason) {
      return; // User cancelled
    }
    
    const response = await fetch(`${API_URL}/api/ope/manager/reject/${employeeId}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ reason: reason })
    });
    
    if (response.ok) {
      const result = await response.json();
      showSuccessPopup(`Rejected ${result.rejected_count} entries for employee ${employeeId}`);
      
      // Close modal if open
      const modals = document.querySelectorAll('.modal-overlay');
      modals.forEach(modal => modal.remove());
      
      // Reload pending data
      const empCode = localStorage.getItem('employee_code');
      await loadPendingData(token, empCode);
      
    } else {
      const errorData = await response.json();
      showErrorPopup(errorData.detail || 'Rejection failed');
    }
    
  } catch (error) {
    console.error('Rejection error:', error);
    showErrorPopup('Network error during rejection');
  }
}

// ✅ NEW: Rejection Reason Popup
function showRejectReasonPopup() {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.6);
      z-index: 99999;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    `;

    const popup = document.createElement('div');
    popup.style.cssText = `
      background: white;
      padding: 35px 30px;
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
      max-width: 500px;
      width: 90%;
      animation: slideUp 0.3s ease;
    `;

    popup.innerHTML = `
      <div style="text-align: center; margin-bottom: 20px;">
        <div style="
          width: 70px;
          height: 70px;
          background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 0 auto 15px;
        ">
          <i class="fas fa-comment-alt" style="font-size: 30px; color: white;"></i>
        </div>
        <h2 style="font-size: 22px; color: #1f2937; margin-bottom: 8px; font-weight: 600;">Rejection Reason</h2>
        <p style="color: #6b7280; font-size: 14px;">Please provide a reason for rejecting these entries</p>
      </div>
      
      <textarea id="rejectionReason" placeholder="Enter rejection reason..." style="
        width: 100%;
        min-height: 120px;
        padding: 12px;
        border: 2px solid #e5e7eb;
        border-radius: 8px;
        font-size: 14px;
        font-family: inherit;
        resize: vertical;
        margin-bottom: 20px;
        box-sizing: border-box;
      "></textarea>
      
      <div style="display: flex; gap: 12px; justify-content: center;">
        <button id="submitRejectBtn" style="
          padding: 12px 28px;
          background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
          color: white;
          border: none;
          border-radius: 10px;
          font-size: 15px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.3s ease;
          box-shadow: 0 4px 12px rgba(239, 68, 68, 0.3);
        ">
          <i class="fas fa-times-circle"></i> Reject
        </button>
        <button id="cancelRejectBtn" style="
          padding: 12px 28px;
          background: #f1f5f9;
          color: #4a5568;
          border: 2px solid #e2e8f0;
          border-radius: 10px;
          font-size: 15px;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.3s ease;
        ">
          Cancel
        </button>
      </div>
    `;

    overlay.appendChild(popup);
    document.body.appendChild(overlay);

    const textarea = document.getElementById('rejectionReason');
    const submitBtn = document.getElementById('submitRejectBtn');
    const cancelBtn = document.getElementById('cancelRejectBtn');

    // Focus textarea
    setTimeout(() => textarea.focus(), 100);

    // Submit button
    submitBtn.addEventListener('click', () => {
      const reason = textarea.value.trim();
      if (!reason) {
        showErrorPopup('Please enter a rejection reason');
        return;
      }
      document.body.removeChild(overlay);
      resolve(reason);
    });

    // Cancel button
    cancelBtn.addEventListener('click', () => {
      document.body.removeChild(overlay);
      resolve(null);
    });

    // Close on overlay click
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        document.body.removeChild(overlay);
        resolve(null);
      }
    });
  });
}