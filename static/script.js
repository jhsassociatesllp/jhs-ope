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
  'sep-oct-2025': { 
    start: '2025-09-21', 
    end: '2025-10-20', 
    display: 'Sep 2025 - Oct 2025' 
  },
  'oct-nov-2025': { 
    start: '2025-10-21', 
    end: '2025-11-20', 
    display: 'Oct 2025 - Nov 2025' 
  },
  'nov-dec-2025': { 
    start: '2025-11-21', 
    end: '2025-12-20', 
    display: 'Nov 2025 - Dec 2025' 
  },
  'dec-jan-2026': {  // ✅ FIXED KEY (removed space)
    start: '2025-12-21', 
    end: '2026-01-20', 
    display: 'Dec 2025 - Jan 2026' 
  }
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
  // ✅ Safety check for empty key
  if (!monthRangeKey) {
    console.error("❌ No month range key provided");
    return null;
  }
  
  // ✅ Check if key exists in monthRanges
  const monthRangeObj = monthRanges[monthRangeKey];
  
  if (!monthRangeObj) {
    console.error("❌ Invalid month range key:", monthRangeKey);
    console.log("📋 Available keys:", Object.keys(monthRanges));
    return null;
  }
  
  // ✅ Check if start property exists
  if (!monthRangeObj.start) {
    console.error("❌ No start date in month range:", monthRangeObj);
    return null;
  }
  
  return monthRangeObj.start;
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
    
    console.log("📅 Month changed to:", selectedMonth);
    
    if (selectedMonth) {
      const startDate = getStartDateForMonth(selectedMonth);
      
      // ✅ CRITICAL FIX: Check if startDate is valid
      if (!startDate) {
        console.error("❌ Could not get start date for month:", selectedMonth);
        showErrorPopup('Invalid month range selected. Please contact support.');
        return;
      }
      
      console.log("✅ Start date:", startDate);
      
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
            } else {
              // Fallback to start date if previous date not found
              dateInput.value = startDate;
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
  // async function loadEmployeeDetails() {
  //   try {
  //     console.log("📡 Fetching employee details...");
  //     const res = await fetch(`${API_URL}/api/employee/${empCode}`, {
  //       headers: {
  //         Authorization: `Bearer ${token}`
  //       }
  //     });

  //     if (!res.ok) {
  //       const err = await res.text();
  //       console.error("❌ API FAILED:", res.status, err);
  //       return;
  //     }

  //     const data = await res.json();
  //     console.log("✅ Employee data received:", data);

  //     const setText = (id, val) => {
  //       const el = document.getElementById(id);
  //       if (el) el.textContent = val ?? "-";
  //     };

  //     setText("empId", data.employee_id);
  //     setText("empName", data.employee_name);
  //     setText("empDesignation", data.designation);
  //     setText("empGender", data.gender);
  //     setText("empPartner", data.partner);
  //     setText("empManager", data.reporting_manager_name);

  //   } catch (err) {
  //     console.error("❌ Fetch crashed:", err);
  //   }
  // }

  // ✅ UPDATED: Load employee details WITH OPE limit
  async function loadEmployeeDetails() {
    const token = localStorage.getItem("access_token");
    const empCode = localStorage.getItem("employee_code");
    
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
      
      // ✅ NEW: Store OPE limit globally
      window.employeeOPELimit = data.ope_limit || 5000;
      
      console.log(`💰 Employee OPE Limit: ₹${window.employeeOPELimit}`);

    } catch (err) {
      console.error("❌ Fetch crashed:", err);
    }
  }

  loadEmployeeDetails();
  
  // ✅ Setup navigation
  setupNavigation();
  checkUserRole();

  // ✅ NEW: Month range change listener - Load saved entries
  // ✅ FIXED: Month range change listener
const monthRangeSelect = document.getElementById('monthRange');
if (monthRangeSelect) {
  monthRangeSelect.addEventListener('change', function() {
    const selectedMonth = this.value;
    const tbody = document.getElementById('entryTableBody');
    const rows = tbody.querySelectorAll('tr');
    
    console.log("📅 Month changed to:", selectedMonth);
    
    if (selectedMonth && rows.length > 0) {
      const startDate = getStartDateForMonth(selectedMonth);
      
      // ✅ CRITICAL FIX: Check if startDate is valid
      if (!startDate) {
        console.error("❌ Could not get start date for month:", selectedMonth);
        showErrorPopup('Invalid month range selected. Please contact support.');
        return;
      }
      
      console.log("✅ Start date:", startDate);
      
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
            } else {
              // Fallback to start date
              dateInput.value = startDate;
            }
          }
        }
      });
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
        // const pdfInput = currentForm.querySelector('#ticketpdf');
        // const pdfFile = pdfInput?.files[0];
        const pdfInput = currentForm.querySelector('#ticketpdf');
        const pdfFile = pdfInput?.files[0];

// ✅ VALIDATE PDF SIZE
if (pdfFile) {
    const fileSizeInMB = pdfFile.size / (1024 * 1024);
    
    if (fileSizeInMB > 10) {
        errors.push(`Entry #${i + 1}: PDF too large (${fileSizeInMB.toFixed(2)}MB). Max: 10MB`);
        errorCount++;
        continue;
    }
    
    if (pdfFile.type !== 'application/pdf') {
        errors.push(`Entry #${i + 1}: Only PDF files allowed`);
        errorCount++;
        continue;
    }
}
        
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
        
        // 2. Check in pending data
        if (!entry && typeof allPendingData !== 'undefined') {
            entry = allPendingData.find(e => e._id === entryId);
        }
        
        // 3. Check in approved data
        if (!entry && typeof allApproveData !== 'undefined') {
            entry = allApproveData.find(e => e._id === entryId);
        }
        
        // 4. Check in rejected data
        if (!entry && typeof allRejectData !== 'undefined') {
            entry = allRejectData.find(e => e._id === entryId);
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
// NEW CODE:
function openPdfModal(base64Pdf) {
    const modal = document.getElementById('pdfModal');
    const viewer = document.getElementById('pdfViewer');
    
    // ✅ Set higher z-index to show in front of employee modal
    modal.style.zIndex = '999999';
    
    viewer.src = `data:application/pdf;base64,${base64Pdf}`;
    modal.classList.add('active');
}

// 7. PDF Modal Close karne ka function
// NEW CODE:
function closePdfModal() {
    const modal = document.getElementById('pdfModal');
    modal.classList.remove('active');
    
    // ✅ Reset z-index
    modal.style.zIndex = '';
    
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

// function setupNavigation() {
//   const navOPE = document.getElementById('navOPE');
//   const navHistory = document.getElementById('navHistory');
//   const navStatus = document.getElementById('navStatus');
//   const navPending = document.getElementById('navPending');
//   const navApprove = document.getElementById('navApprove');
//   const navReject = document.getElementById('navReject');
  
//   const opeSection = document.getElementById('opeSection');
//   const historySection = document.getElementById('historySection');
//   const statusSection = document.getElementById('statusSection');
//   const pendingSection = document.getElementById('pendingSection');
//   const approveSection = document.getElementById('approveSection');
//   const rejectSection = document.getElementById('rejectSection');

//   // Helper function
//   function switchSection(activeNav, activeSection, loadDataCallback) {
//     // Remove active from all nav items
//     document.querySelectorAll('.nav-item').forEach(item => {
//       item.classList.remove('active');
//     });
//     activeNav.classList.add('active');
    
//     // Hide ALL sections properly
//     document.querySelectorAll('.content-section').forEach(section => {
//       section.classList.remove('active');
//       section.style.display = 'none';  
//     });
    
//     // Show selected section
//     if (activeSection) {
//       activeSection.classList.add('active');
//       activeSection.style.display = 'block';  
//     }
    
//     // Close mobile menu
//     if (window.innerWidth <= 768) {
//       document.querySelector('.sidebar').classList.remove('mobile-active');
//     }
    
//     // Load data if callback provided
//     if (loadDataCallback) {
//       loadDataCallback();
//     }
//   }

//   if (navOPE) {
//     navOPE.addEventListener('click', function() {
//       switchSection(navOPE, opeSection);
//     });
//   }

//   // Update the navHistory click event
// if (navHistory) {
//     navHistory.addEventListener('click', async function() {
//         console.log("📌 History nav clicked");
        
//         switchSection(navHistory, historySection, async () => {
//             const token = localStorage.getItem('access_token');
//             const empCode = localStorage.getItem('employee_code');
            
//             console.log("🔑 Token:", token ? "exists" : "missing");
//             console.log("👤 EmpCode:", empCode);
            
//             if (token && empCode) {
//                 console.log("🚀 Loading history data...");
//                 await loadHistoryData(token, empCode);
                
//                 console.log("📊 allHistoryData after load:", allHistoryData);
                
//                 // ✅ CRITICAL FIX: Force display table after loading
//                 displayHistoryTable(allHistoryData);
//             } else {
//                 console.error("❌ Missing token or empCode");
//             }
//         });
//     });
// }

//   if (navStatus) {
//     navStatus.addEventListener('click', async function() {
//         switchSection(navStatus, statusSection, async () => {
//             const token = localStorage.getItem('access_token');
//             const empCode = localStorage.getItem('employee_code');
            
//             if (token && empCode) {
//                 await loadStatusData(token, empCode);
//             }
//         });
//     });
// }

//   if (navPending) {
//     navPending.addEventListener('click', async function() {
//       switchSection(navPending, pendingSection, async () => {
//         const token = localStorage.getItem('access_token');
//         const empCode = localStorage.getItem('employee_code');
        
//         if (token && empCode) {
//           await loadPendingData(token, empCode);
//         }
//       });
//     });
//   }

//   if (navApprove) {
//     navApprove.addEventListener('click', async function() {
//       switchSection(navApprove, approveSection, async () => {
//         const token = localStorage.getItem('access_token');
//         const empCode = localStorage.getItem('employee_code');
        
//         if (token && empCode) {
//           await loadApproveData(token, empCode);
//         }
//       });
//     });
//   }

//   if (navReject) {
//     navReject.addEventListener('click', async function() {
//       switchSection(navReject, rejectSection, async () => {
//         const token = localStorage.getItem('access_token');
//         const empCode = localStorage.getItem('employee_code');
        
//         if (token && empCode) {
//           await loadRejectData(token, empCode);
//         }
//       });
//     });
//   }
// }

// ============================================
// FIXED: setupNavigation function
// ============================================

function setupNavigation() {
  console.log("🔧 Setting up navigation...");
  
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

  // Helper function to switch sections
  function switchSection(activeNav, activeSection, loadDataCallback) {
    console.log("📌 Switching to section:", activeSection?.id || 'unknown');
    
    // Remove active from all nav items
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.remove('active');
    });
    
    if (activeNav) {
      activeNav.classList.add('active');
    }
    
    // Hide ALL sections
    document.querySelectorAll('.content-section').forEach(section => {
      section.classList.remove('active');
      section.style.display = 'none';
    });
    
    // Show selected section
    if (activeSection) {
      activeSection.classList.add('active');
      activeSection.style.display = 'block';
      console.log("✅ Section displayed:", activeSection.id);
    }
    
    // Close mobile menu on navigation
    const sidebar = document.querySelector('.sidebar');
    if (sidebar && sidebar.classList.contains('mobile-active')) {
      sidebar.classList.remove('mobile-active');
      console.log("✅ Mobile menu closed");
    }
    
    // Load data if callback provided
    if (loadDataCallback && typeof loadDataCallback === 'function') {
      console.log("📥 Loading data for section...");
      loadDataCallback();
    }
  }

  // OPE Navigation
  if (navOPE) {
    navOPE.addEventListener('click', function(e) {
      e.preventDefault();
      console.log("📋 OPE clicked");
      switchSection(navOPE, opeSection);
    });
  }

  // History Navigation
  if (navHistory) {
    navHistory.addEventListener('click', async function(e) {
      e.preventDefault();
      console.log("📜 History clicked");
      
      switchSection(navHistory, historySection, async () => {
        const token = localStorage.getItem('access_token');
        const empCode = localStorage.getItem('employee_code');
        
        if (token && empCode) {
          console.log("📥 Loading history data...");
          await loadHistoryData(token, empCode);
          displayHistoryTable(allHistoryData);
        }
      });
    });
  }

  // Status Navigation
  if (navStatus) {
    navStatus.addEventListener('click', async function(e) {
      e.preventDefault();
      console.log("📊 Status clicked");
      
      switchSection(navStatus, statusSection, async () => {
        const token = localStorage.getItem('access_token');
        const empCode = localStorage.getItem('employee_code');
        
        if (token && empCode) {
          console.log("📥 Loading status data...");
          await loadStatusData(token, empCode);
        }
      });
    });
  }

  // Pending Navigation
  if (navPending) {
    navPending.addEventListener('click', async function(e) {
      e.preventDefault();
      console.log("⏳ Pending clicked");
      
      switchSection(navPending, pendingSection, async () => {
        const token = localStorage.getItem('access_token');
        const empCode = localStorage.getItem('employee_code');
        
        if (token && empCode) {
          console.log("📥 Loading pending data...");
          await loadPendingData(token, empCode);
        }
      });
    });
  }

  // Approve Navigation
  if (navApprove) {
    navApprove.addEventListener('click', async function(e) {
      e.preventDefault();
      console.log("✅ Approve clicked");
      
      switchSection(navApprove, approveSection, async () => {
        const token = localStorage.getItem('access_token');
        const empCode = localStorage.getItem('employee_code');
        
        if (token && empCode) {
          console.log("📥 Loading approve data...");
          await loadApproveData(token, empCode);
        }
      });
    });
  }

  // Reject Navigation
  if (navReject) {
    navReject.addEventListener('click', async function(e) {
      e.preventDefault();
      console.log("❌ Reject clicked");
      
      switchSection(navReject, rejectSection, async () => {
        const token = localStorage.getItem('access_token');
        const empCode = localStorage.getItem('employee_code');
        
        if (token && empCode) {
          console.log("📥 Loading reject data...");
          await loadRejectData(token, empCode);
        }
      });
    });
  }

  console.log("✅ Navigation setup complete!");
}

// Make it globally accessible
window.setupNavigation = setupNavigation;

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
        
        // showSuccessPopup(`Date range updated to ${monthRanges[selectedMonth].display}`);
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
      const startDate = getStartDateForMonth(selectedMonth);
      newRowDate = startDate || '';  // ✅ Safety check
    }
  } else {
    // First row - use month start date (21st)
    const startDate = getStartDateForMonth(selectedMonth);
    newRowDate = startDate || '';  // ✅ Safety check
  }
}
  // ✅ If no month selected, leave date empty (no error)
  
  const row = document.createElement('tr');
  row.dataset.rowId = entryCounter;
  
  row.innerHTML = `
    <td><strong>${entryCounter}</strong></td>
    <td><button type="button" onclick="openEntryModal(${entryCounter})" 
                style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); 
                       color: white; 
                       border: none; 
                       padding: 6px 10px; 
                       border-radius: 6px; 
                       cursor: pointer; 
                       display: inline-flex; 
                       align-items: center; 
                       gap: 4px;
                       transition: all 0.2s ease;
                       font-size: 13px;"
                onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(59, 130, 246, 0.4)';"
                onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none';"
                title="Fill form in modal">
          <i class="fas fa-eye"></i>
        </button>
</td>

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
        <option value="food_expence">Food Expence</option>
        <option value="mobile_expence">Mobile Top Up</option>
        <option value="mobile_recharge">Mobile Recharge</option>
        <option value="wifi">Wifi</option>
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
      // ✅ UPDATED: Month range change listener - Load saved entries
const monthRangeSelect = document.getElementById('monthRange');
if (monthRangeSelect) {
  monthRangeSelect.addEventListener('change', async function() {
    const selectedMonth = this.value;
    
    console.log("📅 Month changed to:", selectedMonth);
    
    if (selectedMonth) {
      // ✅ Load saved entries for THIS month ONLY
      await loadSavedEntries();
    } else {
      // ✅ Clear table if no month selected
      const tbody = document.getElementById('entryTableBody');
      tbody.innerHTML = '';
      entryCounter = 0;
    }
  });
}
    });
  }
  
  setTimeout(() => {
    row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, 100);
}

// Open Entry Modal
function openEntryModal(rowId) {
  const modal = document.getElementById('entryFormModal');
  const row = document.querySelector(`tr[data-row-id="${rowId}"]`);
  
  if (!row) return;
  
  // Get current values from row
  const date = row.querySelector(`input[name="date_${rowId}"]`)?.value || '';
  const client = row.querySelector(`input[name="client_${rowId}"]`)?.value || '';
  const projectId = row.querySelector(`input[name="projectid_${rowId}"]`)?.value || '';
  const projectName = row.querySelector(`input[name="projectname_${rowId}"]`)?.value || '';
  const projectType = row.querySelector(`select[name="projecttype_${rowId}"]`)?.value || '';
  const locationFrom = row.querySelector(`input[name="locationfrom_${rowId}"]`)?.value || '';
  const locationTo = row.querySelector(`input[name="locationto_${rowId}"]`)?.value || '';
  const travelMode = row.querySelector(`select[name="travelmode_${rowId}"]`)?.value || '';
  const amount = row.querySelector(`input[name="amount_${rowId}"]`)?.value || '';
  const remarks = row.querySelector(`input[name="remarks_${rowId}"]`)?.value || '';
  
  // Populate modal with current values
  document.getElementById('modalRowId').value = rowId;
  document.getElementById('modalDate').value = date;
  document.getElementById('modalClient').value = client;
  document.getElementById('modalProjectId').value = projectId;
  document.getElementById('modalProjectName').value = projectName;
  document.getElementById('modalProjectType').value = projectType;
  document.getElementById('modalLocationFrom').value = locationFrom;
  document.getElementById('modalLocationTo').value = locationTo;
  document.getElementById('modalTravelMode').value = travelMode;
  document.getElementById('modalAmount').value = amount;
  document.getElementById('modalRemarks').value = remarks;
  document.getElementById('modalFileName').textContent = '';
  
  modal.style.display = 'flex';
  
  // Prevent body scroll
  document.body.style.overflow = 'hidden';
}

// Close Entry Modal
function closeEntryModal() {
  const modal = document.getElementById('entryFormModal');
  modal.style.display = 'none';
  
  // Reset form
  document.getElementById('modalEntryForm').reset();
  document.getElementById('modalFileName').textContent = '';
  
  // Restore body scroll
  document.body.style.overflow = '';
}

// Handle Modal Form Submit
document.addEventListener('DOMContentLoaded', function() {
  const modalForm = document.getElementById('modalEntryForm');
  
  if (modalForm) {
    // PDF file validation
    const pdfInput = document.getElementById('modalTicketPdf');
    const fileName = document.getElementById('modalFileName');

    // ✅ VALIDATE PDF SIZE IN MODAL
pdfInput.addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (!file) return;
    
    const fileSizeInMB = file.size / (1024 * 1024);
    
    if (fileSizeInMB > 10) {
        showErrorPopup(`❌ PDF too large!\n\nSize: ${fileSizeInMB.toFixed(2)}MB\nMax: 10MB`);
        e.target.value = ''; // Clear file
        document.getElementById('modalFileName').textContent = '';
        return;
    }
    
    if (file.type !== 'application/pdf') {
        document.getElementById('modalFileName').textContent = '❌ Only PDF files allowed!';
        document.getElementById('modalFileName').style.color = '#e53e3e';
        e.target.value = '';
    } else {
        document.getElementById('modalFileName').textContent = '✅ ' + file.name;
        document.getElementById('modalFileName').style.color = '#27ae60';
    }
});
    
    pdfInput.addEventListener('change', function(e) {
      const file = e.target.files[0];
      if (!file) {
        fileName.textContent = '';
        return;
      }
      
      if (file.type !== 'application/pdf') {
        fileName.textContent = '❌ Only PDF files allowed!';
        fileName.style.color = '#e53e3e';
        e.target.value = '';
      } else {
        fileName.textContent = '✅ ' + file.name;
        fileName.style.color = '#27ae60';
      }
    });
    
    // Form submission
    modalForm.addEventListener('submit', async function(e) {
      e.preventDefault();
      
      const token = localStorage.getItem('access_token');
      const empCode = localStorage.getItem('employee_code');
      
      if (!token || !empCode) {
        showErrorPopup('Authentication required. Please login again.');
        return;
      }
      
      const rowId = document.getElementById('modalRowId').value;
      const monthRangeSelect = document.getElementById('monthRange');
      const monthRange = monthRangeSelect ? monthRangeSelect.value : '';
      
      if (!monthRange) {
        showErrorPopup('Please select month range first!');
        return;
      }
      
      // Get form values
      const date = document.getElementById('modalDate').value;
      const client = document.getElementById('modalClient').value.trim();
      const projectId = document.getElementById('modalProjectId').value.trim();
      const projectName = document.getElementById('modalProjectName').value.trim();
      const projectType = document.getElementById('modalProjectType').value;
      const locationFrom = document.getElementById('modalLocationFrom').value.trim();
      const locationTo = document.getElementById('modalLocationTo').value.trim();
      const travelMode = document.getElementById('modalTravelMode').value;
      const amount = parseFloat(document.getElementById('modalAmount').value);
      const remarks = document.getElementById('modalRemarks').value.trim();
      const pdfFile = document.getElementById('modalTicketPdf').files[0];
      
      // Validation
      if (!date || !client || !projectId || !projectName || !projectType || 
          !locationFrom || !locationTo || !travelMode || isNaN(amount) || amount <= 0) {
        showErrorPopup('Please fill all required fields correctly');
        return;
      }
      
      if (!isDateInMonthRange(date, monthRange)) {
        const range = monthRanges[monthRange];
        showErrorPopup(
          `❌ Invalid Date!<br><br>` +
          `Selected date: <strong>${date}</strong><br>` +
          `Valid range: <strong>${range.start}</strong> to <strong>${range.end}</strong><br><br>` +
          `Please select a date within <strong>${range.display}</strong> payroll period.`
        );
        return;
      }
      
      if (pdfFile && pdfFile.type !== 'application/pdf') {
        showErrorPopup('Only PDF files allowed');
        return;
      }
      
      // Update table row with modal data
      const row = document.querySelector(`tr[data-row-id="${rowId}"]`);
      if (row) {
        row.querySelector(`input[name="date_${rowId}"]`).value = date;
        row.querySelector(`input[name="client_${rowId}"]`).value = client;
        row.querySelector(`input[name="projectid_${rowId}"]`).value = projectId;
        row.querySelector(`input[name="projectname_${rowId}"]`).value = projectName;
        row.querySelector(`select[name="projecttype_${rowId}"]`).value = projectType;
        row.querySelector(`input[name="locationfrom_${rowId}"]`).value = locationFrom;
        row.querySelector(`input[name="locationto_${rowId}"]`).value = locationTo;
        row.querySelector(`select[name="travelmode_${rowId}"]`).value = travelMode;
        row.querySelector(`input[name="amount_${rowId}"]`).value = amount;
        row.querySelector(`input[name="remarks_${rowId}"]`).value = remarks;
        
        // Handle PDF file
        if (pdfFile) {
          const pdfInput = row.querySelector(`input[name="ticketpdf_${rowId}"]`);
          const dataTransfer = new DataTransfer();
          dataTransfer.items.add(pdfFile);
          pdfInput.files = dataTransfer.files;
        }
      }
      
      // showSuccessPopup('Entry updated successfully in the form!');
      closeEntryModal();
    });
  }
});

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
  
  // showSuccessPopup('Row data copied!');
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
  
  // showSuccessPopup('Data pasted successfully!');
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

// ✅ UPDATED: Save with limit validation and approval level info
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
  
  // ✅ Check for duplicates within current form entries (only among unsaved entries)
  const currentEntries = [];
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const rowId = row.dataset.rowId;
    const savedEntryId = row.dataset.savedEntryId;
    
    // ✅ Only check duplicates for NEW entries (not already saved)
    if (savedEntryId) {
      continue; // Skip already saved entries
    }
    
    const date = row.querySelector(`input[name="date_${rowId}"]`)?.value;
    const client = row.querySelector(`input[name="client_${rowId}"]`)?.value.trim();
    const projectId = row.querySelector(`input[name="projectid_${rowId}"]`)?.value.trim();
    const projectName = row.querySelector(`input[name="projectname_${rowId}"]`)?.value.trim();
    const projectType = row.querySelector(`select[name="projecttype_${rowId}"]`)?.value;
    const locationFrom = row.querySelector(`input[name="locationfrom_${rowId}"]`)?.value.trim();
    const locationTo = row.querySelector(`input[name="locationto_${rowId}"]`)?.value.trim();
    const travelMode = row.querySelector(`select[name="travelmode_${rowId}"]`)?.value;
    const amount = parseFloat(row.querySelector(`input[name="amount_${rowId}"]`)?.value);
    
    if (date && client && projectId && projectName && projectType && locationFrom && locationTo && travelMode && amount > 0) {
      const entryKey = `${date}|${client}|${projectId}|${projectName}|${projectType}|${locationFrom}|${locationTo}|${travelMode}|${amount}`;
      
      if (currentEntries.includes(entryKey)) {
        if (saveBtn) {
          saveBtn.disabled = false;
          saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Entry';
        }
        showErrorPopup(`⚠️ Duplicate Entry Detected in Form!\n\nRow ${i + 1} has the same details as another row you're trying to save. Please check your entries.`);
        return;
      }
      
      currentEntries.push(entryKey);
    }
  }
  
  // Calculate total amount being saved
  let totalAmount = 0;
  
  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    const rowId = row.dataset.rowId;
    const savedEntryId = row.dataset.savedEntryId;
    
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
    // const pdfInput = row.querySelector(`input[name="ticketpdf_${rowId}"]`);
    // const pdfFile = pdfInput?.files[0];
    const pdfInput = row.querySelector(`input[name="ticketpdf_${rowId}"]`);
const pdfFile = pdfInput?.files[0];

// ✅ VALIDATE PDF SIZE
if (pdfFile) {
    const fileSizeInMB = pdfFile.size / (1024 * 1024);
    
    if (fileSizeInMB > 10) {
        showErrorPopup(`❌ PDF file is too large!\n\nFile size: ${fileSizeInMB.toFixed(2)}MB\nMaximum allowed: 10MB\n\nPlease compress your PDF or upload a smaller file.`);
        errorCount++;
        continue; // Skip this entry
    }
    
    if (pdfFile.type !== 'application/pdf') {
        showErrorPopup('❌ Only PDF files are allowed!');
        errorCount++;
        continue;
    }
}
    // ✅ CHANGED: Don't count validation errors - just skip the row
    if (!date || !client || !projectId || !projectName || !projectType || 
        !locationFrom || !locationTo || !travelMode || !amount || parseFloat(amount) <= 0) {
      console.warn(`⚠️ Row ${i + 1}: Missing required fields - skipping`);
      continue; // Skip this row without counting as error
    }
    
    if (!isDateInMonthRange(date, monthRange)) {
      console.warn(`⚠️ Row ${i + 1}: Date ${date} outside valid range - skipping`);
      continue; // Skip this row without counting as error
    }
    
    if (pdfFile && pdfFile.type !== 'application/pdf') {
      console.warn(`⚠️ Row ${i + 1}: Invalid PDF file - skipping`);
      continue; // Skip this row without counting as error
    }
    
    // Add to total
    totalAmount += parseFloat(amount);
    
    try {
      if (savedEntryId) {
        // ✅ UPDATE EXISTING ENTRY
        console.log(`✏️ Updating existing entry: ${savedEntryId}`);
        
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
          row.style.backgroundColor = '#fef3c7';
        } else {
          const errorData = await response.json();
          console.warn(`⚠️ Entry ${i + 1}: ${errorData.detail || 'Update failed'}`);
          // ✅ Don't count as error, don't show to user
        }
        
      } else {
        // ✅ SAVE NEW ENTRY
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
          
          row.dataset.savedEntryId = result.entry_id;
          row.style.backgroundColor = '#f0fdf4';
          
        } else {
          const errorData = await response.json();
          
          // ✅ CHANGED: Silently log error - don't show to user
          if (response.status === 400 && errorData.detail && errorData.detail.includes('Duplicate')) {
            console.warn(`⚠️ Entry ${i + 1}: Duplicate entry (already exists in DB)`);
          } else {
            console.warn(`⚠️ Entry ${i + 1}: ${errorData.detail || 'Save failed'}`);
          }
          // ✅ Don't count as error, don't add to errors array
        }
      }
      
    } catch (err) {
      console.error(`❌ Entry ${i + 1} network error:`, err);
      // ✅ Don't count as error, don't add to errors array
    }
  }
  
  // Re-enable save button
  if (saveBtn) {
    saveBtn.disabled = false;
    saveBtn.innerHTML = '<i class="fas fa-save"></i> Save Entry';
  }
  
  // ✅ ONLY SHOW SUCCESS MESSAGE - NO ERROR POPUPS
  if (successCount > 0) {
    let approvalInfo = '';
    if (totalAmount > window.employeeOPELimit) {
      approvalInfo = `\n\n⚠️ Amount exceeds limit!\nTotal: ₹${totalAmount.toFixed(2)}\nLimit: ₹${window.employeeOPELimit}\n\nThis will require 3-level approval:\n✓ L1: Reporting Manager\n✓ L2: Partner\n✓ L3: HR`;
    } else {
      approvalInfo = `\n\n✅ Within limit!\nTotal: ₹${totalAmount.toFixed(2)}\nLimit: ₹${window.employeeOPELimit}\n\nThis will require 2-level approval:\n✓ L1: Reporting Manager\n✓ L2: HR`;
    }
    
    showSuccessPopup(`${successCount} ${successCount === 1 ? 'entry' : 'entries'} saved successfully!${approvalInfo}`);
  } else {
    // ✅ If nothing was saved, show a gentle message
    showErrorPopup('Please fill at least one complete entry to save.');
  }
}

// ============================================
// SUBMIT ALL ENTRIES - FIXED VERSION
// ============================================
// // ✅ UPDATED: Submit with limit info
// async function submitAllEntries() {
//   const token = localStorage.getItem('access_token');
//   const empCode = localStorage.getItem('employee_code');
  
//   if (!token || !empCode) {
//     showErrorPopup('Authentication required. Please login again.');
//     window.location.href = 'login.html';
//     return;
//   }
  
//   const monthRangeSelect = document.getElementById('monthRange');
//   const monthRange = monthRangeSelect ? monthRangeSelect.value : '';
  
//   if (!monthRange) {
//     showErrorPopup('Please select month range first!');
//     return;
//   }
  
//   const tbody = document.getElementById('entryTableBody');
//   const rows = tbody.querySelectorAll('tr');
  
//   let hasSavedEntries = false;
//   for (const row of rows) {
//     if (row.dataset.savedEntryId) {
//       hasSavedEntries = true;
//       break;
//     }
//   }
  
//   if (!hasSavedEntries) {
//     showErrorPopup('Please save your entries first using "Save Entry" button before submitting!');
//     return;
//   }
  
//   // Confirmation
//   const confirmSubmit = await showConfirmPopup(
//     'Submit Confirmation',
//     'Are you sure you want to submit? After submission, you cannot edit or delete these entries.',
//     'Yes, Submit',
//     'Cancel'
//   );
  
//   if (!confirmSubmit) {
//     return;
//   }
  
//   const submitBtn = document.querySelector('.btn-submit');
//   if (submitBtn) {
//     submitBtn.disabled = true;
//     submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Submitting...';
//   }
  
//   try {
//     console.log(`🚀 Submitting all temporary entries to OPE_data...`);
    
//     const response = await fetch(`${API_URL}/api/ope/submit-final`, {
//       method: 'POST',
//       headers: {
//         'Authorization': `Bearer ${token}`,
//         'Content-Type': 'application/json'
//       },
//       body: JSON.stringify({
//         month_range: monthRange
//       })
//     });
    
//     if (response.ok) {
//       const result = await response.json();
      
//       // ✅ Show detailed success message with approval info
//       let approvalInfo = '';
//       if (result.total_levels === 3) {
//         approvalInfo = `\n\n⚠️ Amount exceeds limit!\nTotal: ₹${result.total_amount.toFixed(2)}\nLimit: ₹${result.ope_limit}\n\nApproval required from:\n1️⃣ Reporting Manager\n2️⃣ Partner\n3️⃣ HR`;
//       } else {
//         approvalInfo = `\n\n✅ Within limit!\nTotal: ₹${result.total_amount.toFixed(2)}\nLimit: ₹${result.ope_limit}\n\nApproval required from:\n1️⃣ Reporting Manager\n2️⃣ HR`;
//       }
      
//       showSuccessPopup(`All entries submitted successfully!

// Total submitted: ${result.submitted_count}${approvalInfo}

// Your entries are now under review.`);
      
//       // Clear the form
//       tbody.innerHTML = '';
//       entryCounter = 0;
//       addNewEntryRow();
      
//       // Reset month selection
//       monthRangeSelect.value = '';
      
//     } else {
//       const errorData = await response.json();
//       showErrorPopup(errorData.detail || 'Submission failed');
//     }
    
//   } catch (err) {
//     console.error(`❌ Submit error:`, err);
//     showErrorPopup(`Network error: ${err.message}`);
//   } finally {
//     if (submitBtn) {
//       submitBtn.disabled = false;
//       submitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Submit All Entries';
//     }
//   }
// }

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
      
      console.log("✅ Submit response:", result);
      
      // ✅ UPDATED: Show detailed success message with cumulative info
      let approvalInfo = '';
      
      if (result.previous_total > 0) {
        // ✅ NOT FIRST SUBMISSION - Show cumulative calculation
        if (result.total_levels === 3) {
          approvalInfo = `\n\n⚠️ Cumulative amount exceeds limit!\n\n` +
                        `📊 Amount Breakdown:\n` +
                        `   Previous Total: ₹${result.previous_total.toFixed(2)}\n` +
                        `   New Entries: +₹${result.new_entries_amount.toFixed(2)}\n` +
                        `   ━━━━━━━━━━━━━━━━━━━━\n` +
                        `   Cumulative Total: ₹${result.total_amount.toFixed(2)}\n` +
                        `   OPE Limit: ₹${result.ope_limit.toFixed(2)}\n\n` +
                        `🔄 Approval required from:\n` +
                        `   1️⃣ Reporting Manager\n` +
                        `   2️⃣ Partner\n` +
                        `   3️⃣ HR`;
        } else {
          approvalInfo = `\n\n✅ Cumulative amount within limit!\n\n` +
                        `📊 Amount Breakdown:\n` +
                        `   Previous Total: ₹${result.previous_total.toFixed(2)}\n` +
                        `   New Entries: +₹${result.new_entries_amount.toFixed(2)}\n` +
                        `   ━━━━━━━━━━━━━━━━━━━━\n` +
                        `   Cumulative Total: ₹${result.total_amount.toFixed(2)}\n` +
                        `   OPE Limit: ₹${result.ope_limit.toFixed(2)}\n\n` +
                        `🔄 Approval required from:\n` +
                        `   1️⃣ Reporting Manager\n` +
                        `   2️⃣ HR`;
        }
      } else {
        // ✅ FIRST SUBMISSION - Normal message
        if (result.total_levels === 3) {
          approvalInfo = `\n\n⚠️ Amount exceeds limit!\n` +
                        `Total: ₹${result.total_amount.toFixed(2)}\n` +
                        `Limit: ₹${result.ope_limit.toFixed(2)}\n\n` +
                        `Approval required from:\n` +
                        `1️⃣ Reporting Manager\n` +
                        `2️⃣ Partner\n` +
                        `3️⃣ HR`;
        } else {
          approvalInfo = `\n\n✅ Within limit!\n` +
                        `Total: ₹${result.total_amount.toFixed(2)}\n` +
                        `Limit: ₹${result.ope_limit.toFixed(2)}\n\n` +
                        `Approval required from:\n` +
                        `1️⃣ Reporting Manager\n` +
                        `2️⃣ HR`;
        }
      }
      
      showSuccessPopup(`All entries submitted successfully!

📦 Total Entries Submitted: ${result.submitted_count}${approvalInfo}

Your entries are now under review.`);
      
      // Clear the form
      tbody.innerHTML = '';
      entryCounter = 0;
      addNewEntryRow();
      
      // Reset month selection
      monthRangeSelect.value = '';
      
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
    // ✅ CLEAR TABLE when no month selected
    const tbody = document.getElementById('entryTableBody');
    tbody.innerHTML = '';
    entryCounter = 0;
    return; // ⬅️ YE IMPORTANT HAI
  }
  
  try {
    console.log("📥 Loading saved entries from Temp_OPE_data...");
    
    const response = await fetch(`${API_URL}/api/ope/temp-history/${empCode}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    if (!response.ok) {
      console.log("No saved entries found");
      const tbody = document.getElementById('entryTableBody');
      tbody.innerHTML = '';
      entryCounter = 0;
      addNewEntryRow(); // ⬅️ BLANK ROW ADD KARO
      return;
    }
    
    const data = await response.json();
    console.log("📦 Temp history response:", data);
    
    const savedEntries = data.history || [];
    console.log("📊 Total saved entries:", savedEntries.length);
    
    // ✅ FORMAT month_range for comparison
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
    
    // ✅ FILTER: ONLY SELECTED MONTH KE ENTRIES
    const filteredEntries = savedEntries.filter(entry => {
      const entry_month = entry.month_range;
      const formatted_entry_month = format_month_range(entry_month);
      
      const matches = entry_month === formatted_month_range || 
                      formatted_entry_month === formatted_month_range ||
                      entry_month === monthRange;
      
      console.log(`Comparing: "${entry_month}" with "${formatted_month_range}" → ${matches ? '✅' : '❌'}`);
      
      return matches;
    });
    
    console.log("✅ Filtered entries for THIS month ONLY:", filteredEntries.length);
    
    // ✅ ALWAYS CLEAR TABLE FIRST
    const tbody = document.getElementById('entryTableBody');
    tbody.innerHTML = '';
    entryCounter = 0;
    
    if (filteredEntries.length === 0) {
      console.log("No saved entries for this month - adding blank row");
      addNewEntryRow(); // ⬅️ BLANK ROW
      return;
    }
    
    console.log(`✅ Loading ${filteredEntries.length} saved entries into form`);
    
    // ✅ LOAD FILTERED ENTRIES
    for (const entry of filteredEntries) {
      entryCounter++;
      
      const row = document.createElement('tr');
      row.dataset.rowId = entryCounter;
      row.dataset.savedEntryId = entry._id;
      row.style.backgroundColor = '#f0fdf4';
      
      row.innerHTML = `
        <td><strong>${entryCounter}</strong></td>
        <td><button type="button" onclick="openEntryModal(${entryCounter})" 
                    style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); 
                           color: white; 
                           border: none; 
                           padding: 6px 10px; 
                           border-radius: 6px; 
                           cursor: pointer;">
              <i class="fas fa-eye"></i>
            </button>
        </td>
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
        <td><input type="text" name="client_${entryCounter}" value="${entry.client}" required /></td>
        <td><input type="text" name="projectid_${entryCounter}" value="${entry.project_id}" required /></td>
        <td><input type="text" name="projectname_${entryCounter}" value="${entry.project_name}" required /></td>
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
        <td><input type="text" name="locationfrom_${entryCounter}" value="${entry.location_from}" required /></td>
        <td><input type="text" name="locationto_${entryCounter}" value="${entry.location_to}" required /></td>
        <td>
          <select name="travelmode_${entryCounter}" required>
            <option value="" disabled>Select Mode</option>
            <option value="metro_recharge" ${entry.travel_mode === 'metro_recharge' ? 'selected' : ''}>Metro Recharge</option>
            <option value="metro_pass" ${entry.travel_mode === 'metro_pass' ? 'selected' : ''}>Metro Pass</option>
            <!-- ...other options... -->
          </select>
        </td>
        <td><input type="number" name="amount_${entryCounter}" value="${entry.amount}" required /></td>
        <td><input type="text" name="remarks_${entryCounter}" value="${entry.remarks || ''}" /></td>
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
    const tbody = document.getElementById('entryTableBody');
    tbody.innerHTML = '';
    entryCounter = 0;
    addNewEntryRow();
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
    console.log(` Deleting entry ${entryId} with month: ${formatted_month_range}`);
    
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
  async function loadEmployeeDetails() {
    const token = localStorage.getItem("access_token");
    const empCode = localStorage.getItem("employee_code");
    
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
      
      // ✅ NEW: Store OPE limit globally
      window.employeeOPELimit = data.ope_limit || 5000;
      
      console.log(`💰 Employee OPE Limit: ₹${window.employeeOPELimit}`);

    } catch (err) {
      console.error("❌ Fetch crashed:", err);
    }
  }
  loadEmployeeDetails();
  setupNavigation();
  checkUserRole();

  // ✅ Load saved entries when month range changes
  const monthRangeSelect = document.getElementById('monthRange');
if (monthRangeSelect) {
  monthRangeSelect.addEventListener('change', async function() {
    const selectedMonth = this.value;
    
    console.log("📅 Month changed to:", selectedMonth);
    
    if (selectedMonth) {
      // ✅ Load saved entries for THIS month ONLY
      await loadSavedEntries();
      
      // ✅ If no saved entries, add blank row
      const tbody = document.getElementById('entryTableBody');
      const rows = tbody.querySelectorAll('tr');
      
      if (rows.length === 0) {
        console.log("No saved entries, adding blank row");
        addNewEntryRow();
      }
      
      // showSuccessPopup(`Date range updated to ${monthRanges[selectedMonth].display}`); 
    }
  });
}

  // if (monthRangeSelect) {
  //   monthRangeSelect.addEventListener('change', function() {
  //     const selectedMonth = this.value;
  //     const tbody = document.getElementById('entryTableBody');
  //     const rows = tbody.querySelectorAll('tr');
      
  //     if (selectedMonth && rows.length > 0) {
  //       const startDate = getStartDateForMonth(selectedMonth);
        
  //       // Update ALL existing rows dates to sequential dates starting from 21st
  //       rows.forEach((row, index) => {
  //         const rowId = row.dataset.rowId;
  //         const dateInput = row.querySelector(`input[name="date_${rowId}"]`);
  //         if (dateInput) {
  //           if (index === 0) {
  //             // First row gets the 21st
  //             dateInput.value = startDate;
  //           } else {
  //             // Subsequent rows get sequential dates
  //             const prevRow = rows[index - 1];
  //             const prevRowId = prevRow.dataset.rowId;
  //             const prevDateInput = prevRow.querySelector(`input[name="date_${prevRowId}"]`);
  //             if (prevDateInput && prevDateInput.value) {
  //               dateInput.value = getNextDate(prevDateInput.value);
  //             }
  //           }
  //         }
  //       });
        
  //       // showSuccessPopup(`Date range updated to ${monthRanges[selectedMonth].display}`);
  //     }
  //   });
  // }
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

// async function loadPendingData(token, empCode) {
//     try {
//         console.log("🔍 Loading pending data for:", empCode);
        
//         document.getElementById('pendingLoadingDiv').style.display = 'block';
//         document.getElementById('pendingTableSection').style.display = 'none';
//         document.getElementById('pendingNoDataDiv').style.display = 'none';

//         // ✅ CHECK IF USER IS HR
//         const isHR = (empCode.trim().toUpperCase() === "JHS729");
        
//         if (isHR) {
//             console.log("👔 Loading HR pending data");
//         } else {
//             console.log("👔 Loading Manager pending data");
//         }

//         const response = await fetch(`${API_URL}/api/ope/manager/pending`, {
//             headers: { 'Authorization': `Bearer ${token}` }
//         });

//         if (!response.ok) {
//             const errorText = await response.text();
//             console.error("❌ Failed to fetch pending:", response.status, errorText);
//             throw new Error('Failed to fetch pending entries');
//         }

//         const data = await response.json();
//         const pendingEmployees = data.employees || [];

//         console.log("✅ Pending employees:", pendingEmployees);
//         console.log("📊 Total pending employees:", pendingEmployees.length);
        
//         // ✅ Store all pending data globally
//         allPendingData = [];
//         pendingEmployees.forEach(emp => {
//             emp.entries.forEach(entry => {
//                 allPendingData.push({
//                     ...entry,
//                     employee_id: emp.employeeId,
//                     employee_name: emp.employeeName,
//                     designation: emp.designation
//                 });
//             });
//         });

//         console.log("📊 Total pending entries:", allPendingData.length);
        
//         if (allPendingData.length === 0) {
//             showPendingNoData();
//         } else {
//             populatePendingMonthFilter();
//             displayPendingEmployeeTable(allPendingData);
//         }
//     } catch (error) {
//         console.error('❌ Error:', error);
//         document.getElementById('pendingLoadingDiv').style.display = 'none';
//         showPendingNoData();
//     }
// }

async function loadPendingData(token, empCode) {
    try {
        console.log("🔍 Loading pending data for:", empCode);
        
        document.getElementById('pendingLoadingDiv').style.display = 'block';
        document.getElementById('pendingTableSection').style.display = 'none';
        document.getElementById('pendingNoDataDiv').style.display = 'none';

        // ✅ CHECK IF USER IS HR
        const isHR = (empCode.trim().toUpperCase() === "JHS729");
        
        if (isHR) {
            console.log("👔 USER IS HR - Fetching L1/L2 approved entries");
            
            // ✅ FOR HR: Get entries where L1 (and L2 for 3-level) are approved
            const response = await fetch(`${API_URL}/api/ope/manager/pending`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error("❌ Failed to fetch HR pending:", response.status, errorText);
                throw new Error('Failed to fetch pending entries');
            }

            const data = await response.json();
            const pendingEmployees = data.employees || [];

            console.log("✅ HR Pending employees:", pendingEmployees);
            console.log("📊 Total pending employees for HR:", pendingEmployees.length);
            
            // ✅ Store all pending data globally
            allPendingData = [];
            pendingEmployees.forEach(emp => {
                emp.entries.forEach(entry => {
                    allPendingData.push({
                        ...entry,
                        employee_id: emp.employeeId,
                        employee_name: emp.employeeName,
                        designation: emp.designation
                    });
                });
            });

            console.log("📊 Total HR pending entries:", allPendingData.length);
            
            if (allPendingData.length === 0) {
                showPendingNoData();
            } else {
                populatePendingMonthFilter();
                displayPendingEmployeeTable(allPendingData);
            }
            
        } else {
            console.log("👔 USER IS MANAGER - Fetching manager pending entries");
            
            const response = await fetch(`${API_URL}/api/ope/manager/pending`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error("❌ Failed to fetch manager pending:", response.status, errorText);
                throw new Error('Failed to fetch pending entries');
            }

            const data = await response.json();
            const pendingEmployees = data.employees || [];

            console.log("✅ Manager Pending employees:", pendingEmployees);
            
            allPendingData = [];
            pendingEmployees.forEach(emp => {
                emp.entries.forEach(entry => {
                    allPendingData.push({
                        ...entry,
                        employee_id: emp.employeeId,
                        employee_name: emp.employeeName,
                        designation: emp.designation
                    });
                });
            });

            if (allPendingData.length === 0) {
                showPendingNoData();
            } else {
                populatePendingMonthFilter();
                displayPendingEmployeeTable(allPendingData);
            }
        }
        
    } catch (error) {
        console.error('❌ Error:', error);
        document.getElementById('pendingLoadingDiv').style.display = 'none';
        showPendingNoData();
    }
}

function populatePendingMonthFilter() {
    const monthSet = new Set();
    
    // Collect all unique months from pending data
    allPendingData.forEach(item => {
        if (item.month_range) monthSet.add(item.month_range);
    });

    // ✅ Create month filter if it doesn't exist
    let filterContainer = document.getElementById('pendingMonthFilterContainer');
    
    if (!filterContainer) {
        // Create filter container if not exists
        const tableSection = document.getElementById('pendingTableSection');
        const filterDiv = document.createElement('div');
        filterDiv.id = 'pendingMonthFilterContainer';
        filterDiv.style.cssText = `
            padding: 15px 20px;
            background: #f8fafc;
            border-bottom: 1px solid #e2e8f0;
            margin-bottom: 15px;
            border-radius: 8px;
        `;
        filterDiv.innerHTML = `
            <label for="pendingMonthFilter" style="display: inline-block; margin-right: 15px; font-weight: 600; color: #475569;">
                <i class="fas fa-filter"></i> Filter by Month:
            </label>
            <select id="pendingMonthFilter" style="
                padding: 8px 12px;
                border: 2px solid #e5e7eb;
                border-radius: 6px;
                font-size: 14px;
                cursor: pointer;
                background: white;
                min-width: 250px;
            "></select>
        `;
        tableSection.parentNode.insertBefore(filterDiv, tableSection);
    }

    const select = document.getElementById('pendingMonthFilter');
    select.innerHTML = '<option value="">All Months</option>';

    Array.from(monthSet).sort().forEach(month => {
        const option = document.createElement('option');
        option.value = month;
        option.textContent = month;
        select.appendChild(option);
    });

    // ✅ Handle month filter change
    select.removeEventListener('change', handlePendingMonthChange);
    select.addEventListener('change', handlePendingMonthChange);
}

function handlePendingMonthChange() {
    const selectedMonth = this.value;
    
    console.log("📅 Pending month filter changed to:", selectedMonth || 'All Months');
    
    if (selectedMonth === '') {
        // Show all pending data
        displayPendingEmployeeTable(allPendingData);
    } else {
        // Filter by selected month - ONLY show employees with pending entries in that month
        const filteredData = allPendingData.filter(item => item.month_range === selectedMonth);
        console.log(`📊 Filtered pending entries for ${selectedMonth}: ${filteredData.length}`);
        displayPendingEmployeeTable(filteredData);
    }
}

function displayPendingEmployeeTable(data) {
    console.log("🎨 Displaying pending employee table");
    
    const tbody = document.getElementById('pendingTableBody');
    if (!tbody) {
        console.error("❌ pendingTableBody not found!");
        return;
    }

    tbody.innerHTML = '';

    if (!data || data.length === 0) {
        showPendingNoData();
        return;
    }

    // ✅ GROUP BY EMPLOYEE - Only include employees with data in current filter
    const groupedByEmployee = {};
    
    data.forEach((entry) => {
        const empId = entry.employee_id || 'Unknown';
        
        if (!groupedByEmployee[empId]) {
            groupedByEmployee[empId] = {
                employeeId: empId,
                employeeName: entry.employee_name || 'Loading...',
                designation: entry.designation || '',
                pendingCount: 0,
                entries: []
            };
        }
        
        groupedByEmployee[empId].pendingCount++;
        groupedByEmployee[empId].entries.push(entry);
    });
    
    console.log("✅ Grouped pending by employee:", Object.keys(groupedByEmployee).length, "employees");
    
    // ✅ DISPLAY EACH EMPLOYEE AS ONE ROW
    Object.values(groupedByEmployee).forEach((employeeData) => {
        const row = document.createElement('tr');
        row.style.cssText = 'transition: background-color 0.2s ease;';
        
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f8fafc';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
        
        row.innerHTML = `
            <td style="text-align: center; font-weight: 600; color: #475569;">
                ${employeeData.employeeId}
            </td>
            <td style="text-align: left;">
                <a href="#" onclick="showPendingEmployeeModal('${employeeData.employeeId}'); return false;" 
                   style="color: #3b82f6; text-decoration: none; font-weight: 600; font-size: 15px; display: flex; align-items: center; gap: 8px;">
                    <i class="fas fa-user-circle" style="font-size: 18px;"></i>
                    ${employeeData.employeeName}
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
                    ${employeeData.pendingCount} Pending
                </span>
            </td>
            <td style="text-align: center;">
                <div style="display: flex; gap: 10px; justify-content: center; align-items: center;">
                    <button onclick="approveEmployee('${employeeData.employeeId}')" 
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
                    <button onclick="rejectEmployee('${employeeData.employeeId}')" 
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

// ✅ NEW: Show pending employee modal with MONTH-FILTERED data
window.showPendingEmployeeModal = function(employeeId) {
    console.log("📋 Opening pending modal for employee:", employeeId);
    
    const monthFilter = document.getElementById('pendingMonthFilter');
    const selectedMonth = monthFilter ? monthFilter.value : '';
    
    let employeeEntries = allPendingData.filter(e => e.employee_id === employeeId);
    
    if (selectedMonth) {
        employeeEntries = employeeEntries.filter(e => e.month_range === selectedMonth);
    }
    
    if (employeeEntries.length === 0) {
        showErrorPopup('No pending entries found for this employee');
        return;
    }
    
    const groupedByMonth = {};
    
    employeeEntries.forEach(entry => {
        const month = entry.month_range || 'Unknown';
        if (!groupedByMonth[month]) {
            groupedByMonth[month] = [];
        }
        groupedByMonth[month].push(entry);
    });
    
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
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
        max-width: 1400px;
        width: 95%;
        max-height: 90vh;
        overflow-y: auto;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    `;

    const employeeName = employeeEntries[0]?.employee_name || employeeId;
    
    let modalContent = `
        <div style="padding: 30px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; border-bottom: 2px solid #e5e7eb; padding-bottom: 15px;">
                <div>
                    <h2 style="font-size: 24px; color: #1e293b; margin-bottom: 5px; display: flex; align-items: center; gap: 10px;">
                        <i class="fas fa-user-clock" style="color: #f59e0b;"></i>
                        ${employeeName}
                    </h2>
                    <p style="color: #64748b; font-size: 14px;">
                        Employee ID: ${employeeId} | Total Pending: ${employeeEntries.length} entries
                        ${selectedMonth ? ` | Month: <strong>${selectedMonth}</strong>` : ' | All Months'}
                    </p>
                </div>
                <button onclick="this.closest('.modal-overlay').remove()" 
                        style="background: #ef4444; color: white; border: none; padding: 10px 20px; 
                               border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.2s;"
                        onmouseover="this.style.background='#dc2626'"
                        onmouseout="this.style.background='#ef4444'">
                    <i class="fas fa-times"></i> Close
                </button>
            </div>
    `;
    
    Object.keys(groupedByMonth).sort().forEach(monthRange => {
        const entries = groupedByMonth[monthRange];
        const totalAmount = entries.reduce((sum, e) => sum + (e.amount || 0), 0);
        
        modalContent += `
            <div style="margin-bottom: 30px; border: 2px solid #e5e7eb; border-radius: 12px; overflow: hidden;">
                <div style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); padding: 15px 20px; display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="color: white; margin: 0; font-size: 18px; display: flex; align-items: center; gap: 10px;">
                        <i class="fas fa-calendar-alt"></i>
                        ${monthRange}
                    </h3>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="background: rgba(255,255,255,0.2); color: white; padding: 6px 12px; border-radius: 8px; font-weight: 600;">
                            Total: ₹${totalAmount.toFixed(2)} | Entries: ${entries.length}
                        </span>
                        <button onclick="editTotalAmount('${employeeId}', '${monthRange}', ${totalAmount})" 
                                style="
                                    background: rgba(255, 255, 255, 0.3);
                                    color: white;
                                    border: 2px solid rgba(255, 255, 255, 0.5);
                                    padding: 6px 12px;
                                    border-radius: 8px;
                                    cursor: pointer;
                                    font-size: 13px;
                                    font-weight: 600;
                                    transition: all 0.2s ease;
                                    backdrop-filter: blur(10px);
                                "
                                onmouseover="this.style.background='rgba(255, 255, 255, 0.4)'; this.style.transform='translateY(-2px)'"
                                onmouseout="this.style.background='rgba(255, 255, 255, 0.3)'; this.style.transform='translateY(0)'">
                            <i class="fas fa-edit"></i> Edit Total
                        </button>
                    </div>
                </div>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead style="background: #f8fafc;">
                            <tr>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Date</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Client</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Project ID</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Project Name</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Type</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">From</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">To</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Mode</th>
                                <th style="padding: 12px; text-align: right; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Amount</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Remarks</th>
                                <th style="padding: 12px; text-align: center; border-bottom: 2px solid #e2e8f0; font-size: 13px;">PDF</th>
                                <th style="padding: 12px; text-align: center; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Action</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        
        entries.forEach(entry => {
            modalContent += `
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 12px; font-size: 13px;">${entry.date || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.client || '-'}</td>
                    <td style="padding: 12px; font-size: 13px; color: #3b82f6; font-weight: 600;">${entry.project_id || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.project_name || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">
                        <span style="background: #fef3c7; color: #92400e; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">
                            ${entry.project_type || '-'}
                        </span>
                    </td>
                    <td style="padding: 12px; font-size: 13px;">${entry.location_from || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.location_to || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${getTravelModeLabel(entry.travel_mode)}</td>
                    <td style="padding: 12px; text-align: right; font-weight: 700; color: #d97706; font-size: 14px;">
                        ₹${entry.amount || 0}
                    </td>
                    <td style="padding: 12px; font-size: 13px; color: #475569; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; cursor: pointer;" 
                        onclick="showFullRemarks('${(entry.remarks || 'NA').replace(/'/g, "&apos;").replace(/"/g, "&quot;")}')"
                        title="Click to view full remarks">
                        ${entry.remarks || 'NA'}
                    </td>
                    <td style="padding: 12px; text-align: center;">
                        ${entry.ticket_pdf
                            ? `<button onclick="viewPdf('${entry._id}', false)" 
                                      style="
                                          background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                                          color: white;
                                          border: none;
                                          padding: 6px 12px;
                                          border-radius: 6px;
                                          cursor: pointer;
                                          font-size: 12px;
                                          font-weight: 600;
                                          transition: all 0.2s ease;
                                          display: inline-flex;
                                          align-items: center;
                                          gap: 4px;
                                      "
                                      onmouseover="this.style.transform='translateY(-2px)'"
                                      onmouseout="this.style.transform='translateY(0)'">
                                  <i class="fas fa-file-pdf"></i> View
                               </button>` 
                            : `<span style="color: #9ca3af; font-size: 12px;">No PDF</span>`}
                    </td>
                    <td style="padding: 12px; text-align: center;">
                        <button onclick="editEntryAmount('${entry._id}', '${employeeId}', ${entry.amount || 0})" 
                                style="
                                    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                                    color: white;
                                    border: none;
                                    padding: 6px 12px;
                                    border-radius: 6px;
                                    cursor: pointer;
                                    font-size: 12px;
                                    font-weight: 600;
                                    transition: all 0.2s ease;
                                "
                                onmouseover="this.style.transform='translateY(-2px)'"
                                onmouseout="this.style.transform='translateY(0)'">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                    </td>
                </tr>
            `;
        });
        
        modalContent += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    });
    
    modalContent += `</div>`;
    
    modal.innerHTML = modalContent;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            overlay.remove();
        }
    });
}

// ✅ NEW: Show Full Remarks Popup
function showFullRemarks(remarks) {
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
        max-width: 600px;
        width: 90%;
        max-height: 70vh;
        overflow-y: auto;
        animation: slideUp 0.3s ease;
    `;

    popup.innerHTML = `
        <div style="text-align: center; margin-bottom: 20px;">
            <div style="
                width: 70px;
                height: 70px;
                background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 15px;
            ">
                <i class="fas fa-comment-alt" style="font-size: 30px; color: white;"></i>
            </div>
            <h2 style="font-size: 22px; color: #1f2937; margin-bottom: 8px; font-weight: 600;">Remarks</h2>
        </div>
        
        <div style="
            background: #f8fafc;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 25px;
            min-height: 100px;
            max-height: 400px;
            overflow-y: auto;
            font-size: 15px;
            line-height: 1.6;
            color: #374151;
            word-wrap: break-word;
            white-space: pre-wrap;
        ">
            ${remarks === 'NA' ? '<span style="color: #9ca3af; font-style: italic;">No remarks provided</span>' : remarks}
        </div>
        
        <div style="display: flex; justify-content: center;">
            <button id="closeRemarksBtn" style="
                padding: 12px 32px;
                background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
                display: flex;
                align-items: center;
                gap: 8px;
            ">
                <i class="fas fa-check"></i> Close
            </button>
        </div>
    `;

    overlay.appendChild(popup);
    document.body.appendChild(overlay);

    const closeBtn = document.getElementById('closeRemarksBtn');

    // Button hover effect
    closeBtn.addEventListener('mouseenter', () => {
        closeBtn.style.transform = 'translateY(-2px)';
        closeBtn.style.boxShadow = '0 6px 16px rgba(59, 130, 246, 0.4)';
    });
    closeBtn.addEventListener('mouseleave', () => {
        closeBtn.style.transform = 'translateY(0)';
        closeBtn.style.boxShadow = '0 4px 12px rgba(59, 130, 246, 0.3)';
    });

    // Close button click
    closeBtn.addEventListener('click', () => {
        overlay.style.opacity = '0';
        overlay.style.transition = 'opacity 0.2s ease';
        setTimeout(() => {
            if (document.body.contains(overlay)) {
                document.body.removeChild(overlay);
            }
        }, 200);
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
        }
    });
}

// Make it globally accessible
window.showFullRemarks = showFullRemarks;

// ✅ Store all pending data globally for filtering
let allPendingData = [];


function showPendingNoData() {
    document.getElementById('pendingLoadingDiv').style.display = 'none';
    document.getElementById('pendingTableSection').style.display = 'none';
    document.getElementById('pendingNoDataDiv').style.display = 'block';
}

// APPROVE SECTION
let allApproveData = [];

// async function loadApproveData(token, empCode) {
//     try {
//         console.log("🔍 Loading approve data for:", empCode);
        
//         document.getElementById('approveLoadingDiv').style.display = 'block';
//         document.getElementById('approveTableSection').style.display = 'none';
//         document.getElementById('approveNoDataDiv').style.display = 'none';

//         // ✅ CHECK IF USER IS HR
//         const isHR = (empCode.trim().toUpperCase() === "JHS729");
        
//         let approvedEmployeeCodes = [];
        
//         if (isHR) {
//             console.log("👔 USER IS HR - Fetching HR approved entries");
            
//             // ✅ FOR HR: Get all employees with fully approved status
//             const statusDocs = await fetch(`${API_URL}/api/ope/hr/approved-employees`, {
//                 headers: { 'Authorization': `Bearer ${token}` }
//             });
            
//             if (statusDocs.ok) {
//                 const data = await statusDocs.json();
//                 approvedEmployeeCodes = data.employee_codes || [];
//             }
//         } else {
//             console.log("👔 USER IS MANAGER - Fetching manager approved entries");
            
//             // ✅ FOR MANAGERS: Use existing logic
//             const approvedListResponse = await fetch(
//                 `${API_URL}/api/ope/manager/approved-list`, 
//                 {
//                     headers: { 'Authorization': `Bearer ${token}` }
//                 }
//             );

//             if (approvedListResponse.ok) {
//                 const approvedListData = await approvedListResponse.json();
//                 approvedEmployeeCodes = approvedListData.employee_codes || [];
//             }
//         }

//         console.log("✅ Approved employees:", approvedEmployeeCodes);

//         if (approvedEmployeeCodes.length === 0) {
//             showApproveNoData();
//             return;
//         }

//         // ✅ Fetch approved entries for each employee
//         allApproveData = [];

//         for (const empCodeLoop of approvedEmployeeCodes) {
//             console.log(`📥 Fetching approved entries for: ${empCodeLoop}`);
            
//             try {
//                 const response = await fetch(
//                     `${API_URL}/api/ope/approved/${empCodeLoop}`, 
//                     {
//                         headers: { 'Authorization': `Bearer ${token}` }
//                     }
//                 );

//                 if (response.ok) {
//                     const data = await response.json();
//                     const approvedCount = data.approved ? data.approved.length : 0;
//                     console.log(`✅ Got ${approvedCount} approved entries for ${empCodeLoop}`);
                    
//                     if (data.approved && data.approved.length > 0) {
//                         allApproveData = allApproveData.concat(data.approved);
//                     }
//                 }
//             } catch (err) {
//                 console.error(`❌ Error fetching ${empCodeLoop}:`, err);
//             }
//         }

//         console.log("\n✅ Total approved entries loaded:", allApproveData.length);

//         if (allApproveData.length === 0) {
//             showApproveNoData();
//         } else {
//             // Remove duplicates
//             const uniqueApproveData = [];
//             const seenIds = new Set();
            
//             allApproveData.forEach(entry => {
//                 if (!seenIds.has(entry._id)) {
//                     seenIds.add(entry._id);
//                     uniqueApproveData.push(entry);
//                 }
//             });
            
//             allApproveData = uniqueApproveData;
//             console.log("✅ After removing duplicates:", allApproveData.length);
            
//             populateApproveMonthFilter();
//             displayApproveEmployeeTable(allApproveData);
//         }
        
//     } catch (error) {
//         console.error('❌ Error in loadApproveData:', error);
//         document.getElementById('approveLoadingDiv').style.display = 'none';
//         showApproveNoData();
//     }
// }

async function loadApproveData(token, empCode) {
    try {
        console.log("🔍 Loading approve data for:", empCode);
        
        document.getElementById('approveLoadingDiv').style.display = 'block';
        document.getElementById('approveTableSection').style.display = 'none';
        document.getElementById('approveNoDataDiv').style.display = 'none';

        // ✅ CHECK IF USER IS HR
        const isHR = (empCode.trim().toUpperCase() === "JHS729");
        
        let approvedEmployeeCodes = [];
        
        if (isHR) {
            console.log("👔 USER IS HR - Fetching HR approved entries");
            
            // ✅ FOR HR: Get all employees with HR approved entries
            const response = await fetch(`${API_URL}/api/ope/hr/approved-employees`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (response.ok) {
                const data = await response.json();
                approvedEmployeeCodes = data.employee_codes || [];
            }
        } else {
            console.log("👔 USER IS MANAGER - Fetching manager approved entries");
            
            const approvedListResponse = await fetch(
                `${API_URL}/api/ope/manager/approved-list`, 
                {
                    headers: { 'Authorization': `Bearer ${token}` }
                }
            );

            if (approvedListResponse.ok) {
                const approvedListData = await approvedListResponse.json();
                approvedEmployeeCodes = approvedListData.employee_codes || [];
            }
        }

        console.log("✅ Approved employees:", approvedEmployeeCodes);

        if (approvedEmployeeCodes.length === 0) {
            showApproveNoData();
            return;
        }

        // ✅ Fetch approved entries for each employee
        allApproveData = [];

        for (const empCodeLoop of approvedEmployeeCodes) {
            console.log(`📥 Fetching approved entries for: ${empCodeLoop}`);
            
            try {
                const response = await fetch(
                    `${API_URL}/api/ope/approved/${empCodeLoop}`, 
                    {
                        headers: { 'Authorization': `Bearer ${token}` }
                    }
                );

                if (response.ok) {
                    const data = await response.json();
                    const approvedCount = data.approved ? data.approved.length : 0;
                    console.log(`✅ Got ${approvedCount} approved entries for ${empCodeLoop}`);
                    
                    if (data.approved && data.approved.length > 0) {
                        allApproveData = allApproveData.concat(data.approved);
                    }
                }
            } catch (err) {
                console.error(`❌ Error fetching ${empCodeLoop}:`, err);
            }
        }

        console.log("\n✅ Total approved entries loaded:", allApproveData.length);

        if (allApproveData.length === 0) {
            showApproveNoData();
        } else {
            // Remove duplicates
            const uniqueApproveData = [];
            const seenIds = new Set();
            
            allApproveData.forEach(entry => {
                if (!seenIds.has(entry._id)) {
                    seenIds.add(entry._id);
                    uniqueApproveData.push(entry);
                }
            });
            
            allApproveData = uniqueApproveData;
            console.log("✅ After removing duplicates:", allApproveData.length);
            
            populateApproveMonthFilter();
            displayApproveEmployeeTable(allApproveData);
        }
        
    } catch (error) {
        console.error('❌ Error in loadApproveData:', error);
        document.getElementById('approveLoadingDiv').style.display = 'none';
        showApproveNoData();
    }
}


function displayApproveEmployeeTable(data) {
    console.log("🎨 Displaying approve employee table");
    
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

    // ✅ GROUP BY EMPLOYEE
    const groupedByEmployee = {};
    
    data.forEach((entry) => {
        const empId = entry.employee_id || 'Unknown';
        
        if (!groupedByEmployee[empId]) {
            groupedByEmployee[empId] = {
                employeeId: empId,
                employeeName: 'Loading...',
                entries: []
            };
        }
        
        groupedByEmployee[empId].entries.push(entry);
    });
    
    console.log("✅ Grouped by employee:", groupedByEmployee);
    
    // ✅ DISPLAY EACH EMPLOYEE AS ONE ROW
    Object.values(groupedByEmployee).forEach((employeeData) => {
        const row = document.createElement('tr');
        row.style.cssText = 'transition: background-color 0.2s ease;';
        
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#f0fdf4';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
        
        // Get employee name from first entry
        const firstName = employeeData.entries[0]?.employee_name || employeeData.employeeId;
        
        row.innerHTML = `
            <td style="text-align: center; font-weight: 600; color: #475569; font-size: 15px;">
                ${employeeData.employeeId}
            </td>
            <td style="text-align: left;">
                <a href="#" onclick="showApprovedEmployeeModal('${employeeData.employeeId}'); return false;" 
                   style="color: #3b82f6; text-decoration: none; font-weight: 600; font-size: 15px; display: flex; align-items: center; gap: 8px;">
                    <i class="fas fa-user-circle" style="font-size: 18px;"></i>
                    ${firstName}
                </a>
            </td>
            <td style="text-align: center;">
                <button onclick="rejectApprovedEmployee('${employeeData.employeeId}')" 
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
                    <i class="fas fa-times-circle"></i> Reject All
                </button>
            </td>
        `;
        
        tbody.appendChild(row);
    });

    document.getElementById('approveLoadingDiv').style.display = 'none';
    document.getElementById('approveTableSection').style.display = 'block';
}

// ✅ UPDATED: Show approved employee modal with MONTH-FILTERED data
window.showApprovedEmployeeModal = function(employeeId) {
    console.log("📋 Opening modal for employee:", employeeId);
    
    // ✅ Get current selected month from filter
    const monthFilter = document.getElementById('approveMonthFilter');
    const selectedMonth = monthFilter ? monthFilter.value : '';
    
    console.log("📅 Selected month filter:", selectedMonth || 'All Months');
    
    // Find employee's approved entries (filtered by month if selected)
    let employeeEntries = allApproveData.filter(e => e.employee_id === employeeId);
    
    // ✅ Apply month filter
    if (selectedMonth) {
        employeeEntries = employeeEntries.filter(e => e.month_range === selectedMonth);
    }
    
    if (employeeEntries.length === 0) {
        showErrorPopup('No approved entries found for this employee');
        return;
    }
    
    // Group by month
    const groupedByMonth = {};
    
    employeeEntries.forEach(entry => {
        const month = entry.month_range || 'Unknown';
        if (!groupedByMonth[month]) {
            groupedByMonth[month] = [];
        }
        groupedByMonth[month].push(entry);
    });
    
    // Create modal
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
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
        max-width: 1400px;
        width: 95%;
        max-height: 90vh;
        overflow-y: auto;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    `;

    // Get employee name
    const employeeName = employeeEntries[0]?.employee_name || employeeId;
    
    let modalContent = `
        <div style="padding: 30px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; border-bottom: 2px solid #e5e7eb; padding-bottom: 15px;">
                <div>
                    <h2 style="font-size: 24px; color: #1e293b; margin-bottom: 5px; display: flex; align-items: center; gap: 10px;">
                        <i class="fas fa-user-check" style="color: #10b981;"></i>
                        ${employeeName}
                    </h2>
                    <p style="color: #64748b; font-size: 14px;">
                        Employee ID: ${employeeId} | Total Approved: ${employeeEntries.length} entries
                        ${selectedMonth ? ` | Month: <strong>${selectedMonth}</strong>` : ' | All Months'}
                    </p>
                </div>
                <button onclick="this.closest('.modal-overlay').remove()" 
                        style="background: #ef4444; color: white; border: none; padding: 10px 20px; 
                               border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.2s;"
                        onmouseover="this.style.background='#dc2626'"
                        onmouseout="this.style.background='#ef4444'">
                    <i class="fas fa-times"></i> Close
                </button>
            </div>
    `;
    
    // Display month-wise data
    Object.keys(groupedByMonth).sort().forEach(monthRange => {
        const entries = groupedByMonth[monthRange];
        const totalAmount = entries.reduce((sum, e) => sum + (e.amount || 0), 0);
        
        modalContent += `
            <div style="margin-bottom: 30px; border: 2px solid #e5e7eb; border-radius: 12px; overflow: hidden;">
                <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 15px 20px; display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="color: white; margin: 0; font-size: 18px; display: flex; align-items: center; gap: 10px;">
                        <i class="fas fa-calendar-alt"></i>
                        ${monthRange}
                    </h3>
                    <span style="background: rgba(255,255,255,0.2); color: white; padding: 6px 12px; border-radius: 8px; font-weight: 600;">
                        Total: ₹${totalAmount.toFixed(2)} | Entries: ${entries.length}
                    </span>
                </div>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead style="background: #f8fafc;">
                            <tr>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Date</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Client</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Project ID</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Project Name</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Type</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">From</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">To</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Mode</th>
                                <th style="padding: 12px; text-align: right; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Amount</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Approved By</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        
        entries.forEach(entry => {
            modalContent += `
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 12px; font-size: 13px;">${entry.date || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.client || '-'}</td>
                    <td style="padding: 12px; font-size: 13px; color: #3b82f6; font-weight: 600;">${entry.project_id || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.project_name || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">
                        <span style="background: #e0e7ff; color: #4338ca; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">
                            ${entry.project_type || '-'}
                        </span>
                    </td>
                    <td style="padding: 12px; font-size: 13px;">${entry.location_from || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.location_to || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${getTravelModeLabel(entry.travel_mode)}</td>
                    <td style="padding: 12px; text-align: right; font-weight: 700; color: #059669; font-size: 14px;">₹${entry.amount || 0}</td>
                    <td style="padding: 12px; font-size: 13px; color: #059669; font-weight: 600;">${entry.approver_name || entry.approved_by || '-'}</td>
                </tr>
            `;
        });
        
        modalContent += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    });
    
    modalContent += `</div>`;
    
    modal.innerHTML = modalContent;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Close on overlay click
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            overlay.remove();
        }
    });
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

    // ✅ Handle month filter change
    select.addEventListener('change', function() {
        const selectedMonth = this.value;
        
        if (selectedMonth === '') {
            // Show all employees
            displayApproveEmployeeTable(allApproveData);
        } else {
            // Filter data by selected month
            const filteredData = allApproveData.filter(item => item.month_range === selectedMonth);
            displayApproveEmployeeTable(filteredData);
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

    // ✅ Remove duplicates
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
    uniqueData.sort((a, b) => 
        new Date(b.date || '1970-01-01') - new Date(a.date || '1970-01-01')
    );

    uniqueData.forEach((entry) => {
        const row = document.createElement('tr');
        
        // ✅ USE approver_name (not approved_by)
        const approverName = entry.approver_name || entry.approved_by || '-';
        
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
            <td>${entry.remarks || 'NA'}</td>
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
                    : '-'}
            </td>
            <td style="color: #059669; font-weight: 600;">${approverName}</td>
            <td style="color: #6b7280; font-size: 13px;">
                ${entry.approved_date 
                    ? new Date(entry.approved_date).toLocaleDateString('en-IN', {
                        day: '2-digit', 
                        month: 'short', 
                        year: 'numeric'
                      })
                    : '-'}
            </td>
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
    
    console.log(`✅ Displayed ${uniqueData.length} approved entries`);
}

function displayApproveTable(data) {
    console.log("🎨 displayApproveTable called");
    console.log("📊 Data length:", data?.length || 0);
    
    const tbody = document.getElementById('approveTableBody');
    if (!tbody) {
        console.error("❌ approveTableBody not found!");
        return;
    }

    tbody.innerHTML = '';

    if (!data || data.length === 0) {
        console.log("📭 No data to display");
        showApproveNoData();
        return;
    }

    // ✅ Remove duplicates
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
    uniqueData.sort((a, b) => 
        new Date(b.date || '1970-01-01') - new Date(a.date || '1970-01-01')
    );

    uniqueData.forEach((entry) => {
        const row = document.createElement('tr');
        
        const approverName = entry.approver_name || entry.approved_by || '-';
        
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
            <td>${entry.remarks || 'NA'}</td>
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
                    : '-'}
            </td>
            <td style="color: #059669; font-weight: 600;">${approverName}</td>
            <td style="color: #6b7280; font-size: 13px;">
                ${entry.approved_date 
                    ? new Date(entry.approved_date).toLocaleDateString('en-IN', {
                        day: '2-digit', 
                        month: 'short', 
                        year: 'numeric'
                      })
                    : '-'}
            </td>
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
    
    console.log(`✅ Displayed ${uniqueData.length} approved entries`);
}

// async function rejectApprovedEmployee(employeeId) {
//     const token = localStorage.getItem('access_token');
    
//     try {
//         console.log("❌ Rejecting all approved entries for:", employeeId);
        
//         const reason = await showRejectReasonPopup();
        
//         if (!reason) {
//             return;
//         }
        
//         // Get all approved entries for this employee
//         const employeeEntries = allApproveData.filter(e => e.employee_id === employeeId);
        
//         if (employeeEntries.length === 0) {
//             showErrorPopup('No approved entries found');
//             return;
//         }
        
//         let rejectedCount = 0;
        
//         for (const entry of employeeEntries) {
//             const response = await fetch(`${API_URL}/api/ope/manager/reject-single`, {
//                 method: 'POST',
//                 headers: {
//                     'Authorization': `Bearer ${token}`,
//                     'Content-Type': 'application/json'
//                 },
//                 body: JSON.stringify({ 
//                     entry_id: entry._id,
//                     employee_id: employeeId,
//                     reason: reason 
//                 })
//             });
            
//             if (response.ok) {
//                 rejectedCount++;
//             }
//         }
        
//         if (rejectedCount > 0) {
//             showSuccessPopup(`Rejected ${rejectedCount} entries for employee ${employeeId}`);
            
//             // Reload approve data
//             const empCode = localStorage.getItem('employee_code');
//             await loadApproveData(token, empCode);
//         }
        
//     } catch (error) {
//         console.error('Rejection error:', error);
//         showErrorPopup('Network error during rejection');
//     }
// }

async function rejectApprovedEmployee(employeeId) {
    const token = localStorage.getItem('access_token');
    const currentEmpCode = localStorage.getItem('employee_code');
    
    try {
        console.log("❌ Rejecting all approved entries for:", employeeId);
        
        const reason = await showRejectReasonPopup();
        
        if (!reason) {
            return;
        }
        
        // Get all approved entries for this employee
        const employeeEntries = allApproveData.filter(e => e.employee_id === employeeId);
        
        if (employeeEntries.length === 0) {
            showErrorPopup('No approved entries found');
            return;
        }
        
        let rejectedCount = 0;
        
        // ✅ CHECK IF USER IS HR
        const isHR = (currentEmpCode.toUpperCase() === "JHS729");
        
        if (isHR) {
            // ✅ HR BULK REJECT
            const response = await fetch(`${API_URL}/api/ope/hr/reject/${employeeId}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ reason: reason })
            });
            
            if (response.ok) {
                const result = await response.json();
                showSuccessPopup(`HR rejected ${result.rejected_count} entries for employee ${employeeId}`);
                
                // Reload approve and reject data
                await loadApproveData(token, currentEmpCode);
                await loadRejectData(token, currentEmpCode);
            } else {
                const errorData = await response.json();
                showErrorPopup(errorData.detail || 'Rejection failed');
            }
        } else {
            // ✅ MANAGER SINGLE-ENTRY REJECT
            for (const entry of employeeEntries) {
                const response = await fetch(`${API_URL}/api/ope/manager/reject-single`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ 
                        entry_id: entry._id,
                        employee_id: employeeId,
                        reason: reason 
                    })
                });
                
                if (response.ok) {
                    rejectedCount++;
                }
            }
            
            if (rejectedCount > 0) {
                showSuccessPopup(`Rejected ${rejectedCount} entries for employee ${employeeId}`);
                
                // Reload approve and reject data
                await loadApproveData(token, currentEmpCode);
                await loadRejectData(token, currentEmpCode);
            }
        }
        
    } catch (error) {
        console.error('Rejection error:', error);
        showErrorPopup('Network error during rejection');
    }
}

// Make it global
window.rejectApprovedEmployee = rejectApprovedEmployee;

function showApprovedEmployeeModal(employeeId) {
    console.log("📋 Opening modal for employee:", employeeId);
    
    // Find employee's approved entries
    const employeeEntries = allApproveData.filter(e => e.employee_id === employeeId);
    
    if (employeeEntries.length === 0) {
        showErrorPopup('No approved entries found for this employee');
        return;
    }
    
    // Group by month
    const groupedByMonth = {};
    
    employeeEntries.forEach(entry => {
        const month = entry.month_range || 'Unknown';
        if (!groupedByMonth[month]) {
            groupedByMonth[month] = [];
        }
        groupedByMonth[month].push(entry);
    });
    
    // Create modal
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
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
        max-width: 1400px;
        width: 95%;
        max-height: 90vh;
        overflow-y: auto;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    `;

    // Get employee name
    const employeeName = employeeEntries[0]?.employee_name || employeeId;
    
    let modalContent = `
        <div style="padding: 30px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; border-bottom: 2px solid #e5e7eb; padding-bottom: 15px;">
                <div>
                    <h2 style="font-size: 24px; color: #1e293b; margin-bottom: 5px; display: flex; align-items: center; gap: 10px;">
                        <i class="fas fa-user-check" style="color: #10b981;"></i>
                        ${employeeName}
                    </h2>
                    <p style="color: #64748b; font-size: 14px;">
                        Employee ID: ${employeeId} | Total Approved: ${employeeEntries.length} entries
                    </p>
                </div>
                <button onclick="this.closest('.modal-overlay').remove()" 
                        style="background: #ef4444; color: white; border: none; padding: 10px 20px; 
                               border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.2s;"
                        onmouseover="this.style.background='#dc2626'"
                        onmouseout="this.style.background='#ef4444'">
                    <i class="fas fa-times"></i> Close
                </button>
            </div>
    `;
    
    // Display month-wise data
    Object.keys(groupedByMonth).sort().forEach(monthRange => {
        const entries = groupedByMonth[monthRange];
        const totalAmount = entries.reduce((sum, e) => sum + (e.amount || 0), 0);
        
        modalContent += `
            <div style="margin-bottom: 30px; border: 2px solid #e5e7eb; border-radius: 12px; overflow: hidden;">
                <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 15px 20px; display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="color: white; margin: 0; font-size: 18px; display: flex; align-items: center; gap: 10px;">
                        <i class="fas fa-calendar-alt"></i>
                        ${monthRange}
                    </h3>
                    <span style="background: rgba(255,255,255,0.2); color: white; padding: 6px 12px; border-radius: 8px; font-weight: 600;">
                        Total: ₹${totalAmount.toFixed(2)} | Entries: ${entries.length}
                    </span>
                </div>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead style="background: #f8fafc;">
                            <tr>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Date</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Client</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Project ID</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Project Name</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Type</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">From</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">To</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Mode</th>
                                <th style="padding: 12px; text-align: right; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Amount</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; font-size: 13px;">Approved By</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        
        entries.forEach(entry => {
            modalContent += `
                <tr style="border-bottom: 1px solid #f1f5f9;">
                    <td style="padding: 12px; font-size: 13px;">${entry.date || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.client || '-'}</td>
                    <td style="padding: 12px; font-size: 13px; color: #3b82f6; font-weight: 600;">${entry.project_id || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.project_name || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">
                        <span style="background: #e0e7ff; color: #4338ca; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">
                            ${entry.project_type || '-'}
                        </span>
                    </td>
                    <td style="padding: 12px; font-size: 13px;">${entry.location_from || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.location_to || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${getTravelModeLabel(entry.travel_mode)}</td>
                    <td style="padding: 12px; text-align: right; font-weight: 700; color: #059669; font-size: 14px;">₹${entry.amount || 0}</td>
                    <td style="padding: 12px; font-size: 13px; color: #059669; font-weight: 600;">${entry.approver_name || entry.approved_by || '-'}</td>
                </tr>
            `;
        });
        
        modalContent += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    });
    
    modalContent += `</div>`;
    
    modal.innerHTML = modalContent;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Close on overlay click
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            overlay.remove();
        }
    });
}

// Make it global
window.showApprovedEmployeeModal = showApprovedEmployeeModal;


function showApproveNoData() {
    document.getElementById('approveLoadingDiv').style.display = 'none';
    document.getElementById('approveTableSection').style.display = 'none';
    document.getElementById('approveNoDataDiv').style.display = 'block';
}

// REJECT SECTION
let allRejectData = [];

// async function loadRejectData(token, empCode) {
//     try {
//         console.log("🔍 Loading reject data for manager:", empCode);
        
//         document.getElementById('rejectLoadingDiv').style.display = 'block';
//         document.getElementById('rejectTableSection').style.display = 'none';
//         document.getElementById('rejectNoDataDiv').style.display = 'none';

//         const rejectedListResponse = await fetch(
//             `${API_URL}/api/ope/manager/rejected-list`, 
//             {
//                 headers: { 'Authorization': `Bearer ${token}` }
//             }
//         );

//         if (!rejectedListResponse.ok) {
//             console.error("❌ Failed to fetch rejected list:", rejectedListResponse.status);
//             throw new Error('Failed to fetch rejected list');
//         }

//         const rejectedListData = await rejectedListResponse.json();
//         const rejectedEmployeeCodes = rejectedListData.employee_codes || [];

//         console.log("✅ Rejected employees:", rejectedEmployeeCodes);

//         if (rejectedEmployeeCodes.length === 0) {
//             console.log("📭 No rejected employees found");
//             showRejectNoData();
//             return;
//         }

//         // ✅ Fetch rejected entries for EACH employee
//         allRejectData = [];

//         for (const empCodeLoop of rejectedEmployeeCodes) {
//             console.log(`📥 Fetching rejected entries for: ${empCodeLoop}`);
            
//             try {
//                 const response = await fetch(
//                     `${API_URL}/api/ope/rejected/${empCodeLoop}`, 
//                     {
//                         headers: { 'Authorization': `Bearer ${token}` }
//                     }
//                 );

//                 if (response.ok) {
//                     const data = await response.json();
//                     const rejectedCount = data.rejected ? data.rejected.length : 0;
//                     console.log(`✅ Got ${rejectedCount} rejected entries for ${empCodeLoop}`);
                    
//                     if (data.rejected && data.rejected.length > 0) {
//                         allRejectData = allRejectData.concat(data.rejected);
//                     }
//                 } else {
//                     console.error(`❌ Failed to fetch for ${empCodeLoop}:`, response.status);
//                 }
//             } catch (err) {
//                 console.error(`❌ Error fetching ${empCodeLoop}:`, err);
//             }
//         }

//         console.log("\n✅ Total rejected entries loaded:", allRejectData.length);

//         if (allRejectData.length === 0) {
//             console.log("📭 No rejected entries found");
//             showRejectNoData();
//         } else {
//             // ✅ Populate month filter first, then display employee table
//             populateRejectMonthFilter();
//             displayRejectEmployeeTable(allRejectData);
//         }
        
//     } catch (error) {
//         console.error('❌ Error in loadRejectData:', error);
//         document.getElementById('rejectLoadingDiv').style.display = 'none';
//         showRejectNoData();
//     }
// }  


// function displayRejectEmployeeTable(data) {
//     console.log("🎨 Displaying reject employee table");
    
//     const tbody = document.getElementById('rejectTableBody');
//     if (!tbody) {
//         console.error("❌ rejectTableBody not found!");
//         return;
//     }

//     tbody.innerHTML = '';

//     if (!data || data.length === 0) {
//         showRejectNoData();
//         return;
//     }

//     // ✅ GROUP BY EMPLOYEE
//     const groupedByEmployee = {};
    
//     data.forEach((entry) => {
//         const empId = entry.employee_id || 'Unknown';
        
//         if (!groupedByEmployee[empId]) {
//             groupedByEmployee[empId] = {
//                 employeeId: empId,
//                 employeeName: 'Loading...',
//                 rejectedCount: 0,
//                 entries: []
//             };
//         }
        
//         groupedByEmployee[empId].rejectedCount++;
//         groupedByEmployee[empId].entries.push(entry);
//     });
    
//     console.log("✅ Grouped by employee:", groupedByEmployee);
    
//     // ✅ DISPLAY EACH EMPLOYEE AS ONE ROW
//     Object.values(groupedByEmployee).forEach((employeeData) => {
//         const row = document.createElement('tr');
//         row.style.cssText = 'transition: background-color 0.2s ease;';
        
//         row.addEventListener('mouseenter', function() {
//             this.style.backgroundColor = '#fef2f2';
//         });
//         row.addEventListener('mouseleave', function() {
//             this.style.backgroundColor = '';
//         });
        
//         // Get employee name from first entry
//         const firstName = employeeData.entries[0]?.employee_name || employeeData.employeeId;
        
//         row.innerHTML = `
//             <td style="text-align: center; font-weight: 600; color: #475569; font-size: 15px;">
//                 ${employeeData.employeeId}
//             </td>
//             <td style="text-align: left;">
//                 <a href="#" onclick="showRejectedEmployeeModal('${employeeData.employeeId}'); return false;" 
//                    style="color: #ef4444; text-decoration: none; font-weight: 600; font-size: 15px; display: flex; align-items: center; gap: 8px;">
//                     <i class="fas fa-user-times" style="font-size: 18px;"></i>
//                     ${firstName}
//                 </a>
//             </td>
//             <td style="text-align: center;">
//                 <button onclick="approveRejectedEmployee('${employeeData.employeeId}')" 
//                         style="
//                             padding: 10px 20px; 
//                             background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
//                             color: white; 
//                             border: none; 
//                             border-radius: 8px; 
//                             cursor: pointer; 
//                             font-weight: 600; 
//                             font-size: 14px;
//                             display: inline-flex; 
//                             align-items: center; 
//                             gap: 6px;
//                             transition: all 0.3s ease;
//                             box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
//                         "
//                         onmouseover="this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 12px rgba(16, 185, 129, 0.4)';"
//                         onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(16, 185, 129, 0.3)';">
//                     <i class="fas fa-check-circle"></i> Approve All
//                 </button>
//             </td>
//         `;
        
//         tbody.appendChild(row);
//     });

//     document.getElementById('rejectLoadingDiv').style.display = 'none';
//     document.getElementById('rejectTableSection').style.display = 'block';
    
//     console.log(`✅ Displayed ${Object.keys(groupedByEmployee).length} rejected employees`);
// }

async function loadRejectData(token, empCode) {
    try {
        console.log("🔍 Loading reject data for:", empCode);
        
        document.getElementById('rejectLoadingDiv').style.display = 'block';
        document.getElementById('rejectTableSection').style.display = 'none';
        document.getElementById('rejectNoDataDiv').style.display = 'none';

        // ✅ CHECK IF USER IS HR
        const isHR = (empCode.trim().toUpperCase() === "JHS729");
        
        let rejectedEmployeeCodes = [];
        
        if (isHR) {
            console.log("👔 USER IS HR - Fetching HR rejected entries");
            
            const response = await fetch(`${API_URL}/api/ope/hr/rejected-employees`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            
            if (response.ok) {
                const data = await response.json();
                rejectedEmployeeCodes = data.employee_codes || [];
            }
        } else {
            console.log("👔 USER IS MANAGER - Fetching manager rejected entries");
            
            const rejectedListResponse = await fetch(
                `${API_URL}/api/ope/manager/rejected-list`, 
                {
                    headers: { 'Authorization': `Bearer ${token}` }
                }
            );

            if (rejectedListResponse.ok) {
                const rejectedListData = await rejectedListResponse.json();
                rejectedEmployeeCodes = rejectedListData.employee_codes || [];
            }
        }

        console.log("✅ Rejected employees:", rejectedEmployeeCodes);

        if (rejectedEmployeeCodes.length === 0) {
            showRejectNoData();
            return;
        }

        allRejectData = [];

        for (const empCodeLoop of rejectedEmployeeCodes) {
            console.log(`📥 Fetching rejected entries for: ${empCodeLoop}`);
            
            try {
                const response = await fetch(
                    `${API_URL}/api/ope/rejected/${empCodeLoop}`, 
                    {
                        headers: { 'Authorization': `Bearer ${token}` }
                    }
                );

                if (response.ok) {
                    const data = await response.json();
                    if (data.rejected && data.rejected.length > 0) {
                        allRejectData = allRejectData.concat(data.rejected);
                    }
                }
            } catch (err) {
                console.error(`❌ Error fetching ${empCodeLoop}:`, err);
            }
        }

        if (allRejectData.length === 0) {
            showRejectNoData();
        } else {
            populateRejectMonthFilter();
            displayRejectEmployeeTable(allRejectData);
        }
        
    } catch (error) {
        console.error('❌ Error in loadRejectData:', error);
        document.getElementById('rejectLoadingDiv').style.display = 'none';
        showRejectNoData();
    }
}


function displayRejectEmployeeTable(data) {
    console.log("🎨 Displaying reject employee table");
    
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

    // ✅ GROUP BY EMPLOYEE
    const groupedByEmployee = {};
    
    data.forEach((entry) => {
        const empId = entry.employee_id || 'Unknown';
        
        if (!groupedByEmployee[empId]) {
            groupedByEmployee[empId] = {
                employeeId: empId,
                employeeName: 'Loading...',
                rejectedCount: 0,
                entries: []
            };
        }
        
        groupedByEmployee[empId].rejectedCount++;
        groupedByEmployee[empId].entries.push(entry);
    });
    
    console.log("✅ Grouped by employee:", groupedByEmployee);
    
    // ✅ DISPLAY EACH EMPLOYEE AS ONE ROW
    Object.values(groupedByEmployee).forEach((employeeData) => {
        const row = document.createElement('tr');
        row.style.cssText = 'transition: background-color 0.2s ease;';
        
        row.addEventListener('mouseenter', function() {
            this.style.backgroundColor = '#fef2f2';
        });
        row.addEventListener('mouseleave', function() {
            this.style.backgroundColor = '';
        });
        
        // Get employee name from first entry
        const firstName = employeeData.entries[0]?.employee_name || employeeData.employeeId;
        
        row.innerHTML = `
            <td style="text-align: center; font-weight: 600; color: #475569; font-size: 15px;">
                ${employeeData.employeeId}
            </td>
            <td style="text-align: left;">
                <a href="#" onclick="showRejectedEmployeeModal('${employeeData.employeeId}'); return false;" 
                   style="color: #ef4444; text-decoration: none; font-weight: 600; font-size: 15px; display: flex; align-items: center; gap: 8px;">
                    <i class="fas fa-user-times" style="font-size: 18px;"></i>
                    ${firstName}
                </a>
            </td>
            <td style="text-align: center;">
                <button onclick="approveRejectedEmployee('${employeeData.employeeId}')" 
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
                    <i class="fas fa-check-circle"></i> Approve All
                </button>
            </td>
        `;
        
        tbody.appendChild(row);
    });

    document.getElementById('rejectLoadingDiv').style.display = 'none';
    document.getElementById('rejectTableSection').style.display = 'block';
}

// ✅ UPDATED: Show rejected employee modal with MONTH-FILTERED data
window.showRejectedEmployeeModal = function(employeeId) {
    console.log("📋 Opening rejected modal for employee:", employeeId);
    
    // ✅ Get current selected month from filter
    const monthFilter = document.getElementById('rejectMonthFilter');
    const selectedMonth = monthFilter ? monthFilter.value : '';
    
    console.log("📅 Selected month filter:", selectedMonth || 'All Months');
    
    // ✅ Find employee's rejected entries (filtered by month if selected)
    let employeeEntries = allRejectData.filter(e => e.employee_id === employeeId);
    
    // ✅ CRITICAL FIX: Remove duplicates based on _id
    const seenIds = new Set();
    employeeEntries = employeeEntries.filter(entry => {
        const entryId = entry._id;
        if (seenIds.has(entryId)) {
            console.log(`⚠️ Skipping duplicate entry: ${entryId}`);
            return false;
        }
        seenIds.add(entryId);
        return true;
    });
    
    console.log(`✅ After removing duplicates: ${employeeEntries.length} unique entries`);
    
    // ✅ Apply month filter
    if (selectedMonth) {
        employeeEntries = employeeEntries.filter(e => e.month_range === selectedMonth);
        console.log(`✅ After month filter: ${employeeEntries.length} entries`);
    }
    
    if (employeeEntries.length === 0) {
        showErrorPopup('No rejected entries found for this employee');
        return;
    }
    
    // Group by month
    const groupedByMonth = {};
    
    employeeEntries.forEach(entry => {
        const month = entry.month_range || 'Unknown';
        if (!groupedByMonth[month]) {
            groupedByMonth[month] = [];
        }
        groupedByMonth[month].push(entry);
    });
    
    // Create modal
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
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
        max-width: 1400px;
        width: 95%;
        max-height: 90vh;
        overflow-y: auto;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    `;

    // Get employee name
    const employeeName = employeeEntries[0]?.employee_name || employeeId;
    
    let modalContent = `
        <div style="padding: 30px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; border-bottom: 2px solid #e5e7eb; padding-bottom: 15px;">
                <div>
                    <h2 style="font-size: 24px; color: #1e293b; margin-bottom: 5px; display: flex; align-items: center; gap: 10px;">
                        <i class="fas fa-user-times" style="color: #ef4444;"></i>
                        ${employeeName}
                    </h2>
                    <p style="color: #64748b; font-size: 14px;">
                        Employee ID: ${employeeId} | Total Rejected: ${employeeEntries.length} entries
                        ${selectedMonth ? ` | Month: <strong>${selectedMonth}</strong>` : ' | All Months'}
                    </p>
                </div>
                <button onclick="this.closest('.modal-overlay').remove()" 
                        style="background: #ef4444; color: white; border: none; padding: 10px 20px; 
                               border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.2s;"
                        onmouseover="this.style.background='#dc2626'"
                        onmouseout="this.style.background='#ef4444'">
                    <i class="fas fa-times"></i> Close
                </button>
            </div>
    `;
    
    // Display month-wise data
    Object.keys(groupedByMonth).sort().forEach(monthRange => {
        const entries = groupedByMonth[monthRange];
        const totalAmount = entries.reduce((sum, e) => sum + (e.amount || 0), 0);
        
        modalContent += `
            <div style="margin-bottom: 30px; border: 2px solid #fee2e2; border-radius: 12px; overflow: hidden;">
                <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 15px 20px; display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="color: white; margin: 0; font-size: 18px; display: flex; align-items: center; gap: 10px;">
                        <i class="fas fa-calendar-alt"></i>
                        ${monthRange}
                    </h3>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="background: rgba(255,255,255,0.2); color: white; padding: 6px 12px; border-radius: 8px; font-weight: 600;">
                            Total: ₹${totalAmount.toFixed(2)} | Entries: ${entries.length}
                        </span>
                        <button onclick="editTotalAmount('${employeeId}', '${monthRange}', ${totalAmount})" 
                                style="
                                    background: rgba(255, 255, 255, 0.3);
                                    color: white;
                                    border: 2px solid rgba(255, 255, 255, 0.5);
                                    padding: 6px 12px;
                                    border-radius: 8px;
                                    cursor: pointer;
                                    font-size: 13px;
                                    font-weight: 600;
                                    transition: all 0.2s ease;
                                    backdrop-filter: blur(10px);
                                "
                                onmouseover="this.style.background='rgba(255, 255, 255, 0.4)'; this.style.transform='translateY(-2px)'"
                                onmouseout="this.style.background='rgba(255, 255, 255, 0.3)'; this.style.transform='translateY(0)'">
                            <i class="fas fa-edit"></i> Edit Total
                        </button>
                    </div>
                </div>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead style="background: #fef2f2;">
                            <tr>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Date</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Client</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Project ID</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Project Name</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Type</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">From</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">To</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Mode</th>
                                <th style="padding: 12px; text-align: right; border-bottom: 2px solid #fee2e2; font-size: 13px;">Amount</th>
                                <th style="padding: 12px; text-align: center; border-bottom: 2px solid #fee2e2; font-size: 13px;">Action</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Rejected By</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Reason</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        
        entries.forEach(entry => {
            modalContent += `
                <tr style="border-bottom: 1px solid #fef2f2;">
                    <td style="padding: 12px; font-size: 13px;">${entry.date || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.client || '-'}</td>
                    <td style="padding: 12px; font-size: 13px; color: #3b82f6; font-weight: 600;">${entry.project_id || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.project_name || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">
                        <span style="background: #fee2e2; color: #991b1b; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">
                            ${entry.project_type || '-'}
                        </span>
                    </td>
                    <td style="padding: 12px; font-size: 13px;">${entry.location_from || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.location_to || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${getTravelModeLabel(entry.travel_mode)}</td>
                    <td style="padding: 12px; text-align: right; font-weight: 700; color: #dc2626; font-size: 14px;">₹${entry.amount || 0}</td>
                    <td style="padding: 12px; text-align: center;">
                        <button onclick="editEntryAmount('${entry._id}', '${employeeId}', ${entry.amount || 0})" 
                                style="
                                    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                                    color: white;
                                    border: none;
                                    padding: 6px 12px;
                                    border-radius: 6px;
                                    cursor: pointer;
                                    font-size: 12px;
                                    font-weight: 600;
                                    transition: all 0.2s ease;
                                "
                                onmouseover="this.style.transform='translateY(-2px)'"
                                onmouseout="this.style.transform='translateY(0)'">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                    </td>
                    <td style="padding: 12px; font-size: 13px; color: #dc2626; font-weight: 600;">${entry.rejector_name || entry.rejected_by || '-'}</td>
                    <td style="padding: 12px; font-size: 12px; color: #dc2626; max-width: 200px;">
                        <div style="max-height: 60px; overflow-y: auto;">
                            ${entry.rejection_reason || '-'}
                        </div>
                    </td>
                </tr>
            `;
        });
        
        modalContent += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    });
    
    modalContent += `</div>`;
    
    modal.innerHTML = modalContent;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Close on overlay click
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            overlay.remove();
        }
    });
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

    // ✅ Handle month filter change
    select.addEventListener('change', function() {
        const selectedMonth = this.value;
        
        if (selectedMonth === '') {
            // Show all employees
            displayRejectEmployeeTable(allRejectData);
        } else {
            // Filter data by selected month
            const filteredData = allRejectData.filter(item => item.month_range === selectedMonth);
            displayRejectEmployeeTable(filteredData);
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

function showRejectedEmployeeModal(employeeId) {
    console.log("📋 Opening rejected modal for employee:", employeeId);
    
    // Find employee's rejected entries
    const employeeEntries = allRejectData.filter(e => e.employee_id === employeeId);
    
    if (employeeEntries.length === 0) {
        showErrorPopup('No rejected entries found for this employee');
        return;
    }
    
    // Group by month
    const groupedByMonth = {};
    
    employeeEntries.forEach(entry => {
        const month = entry.month_range || 'Unknown';
        if (!groupedByMonth[month]) {
            groupedByMonth[month] = [];
        }
        groupedByMonth[month].push(entry);
    });
    
    // Create modal
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
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
        max-width: 1400px;
        width: 95%;
        max-height: 90vh;
        overflow-y: auto;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    `;

    // Get employee name
    const employeeName = employeeEntries[0]?.employee_name || employeeId;
    
    let modalContent = `
        <div style="padding: 30px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; border-bottom: 2px solid #e5e7eb; padding-bottom: 15px;">
                <div>
                    <h2 style="font-size: 24px; color: #1e293b; margin-bottom: 5px; display: flex; align-items: center; gap: 10px;">
                        <i class="fas fa-user-times" style="color: #ef4444;"></i>
                        ${employeeName}
                    </h2>
                    <p style="color: #64748b; font-size: 14px;">
                        Employee ID: ${employeeId} | Total Rejected: ${employeeEntries.length} entries
                    </p>
                </div>
                <button onclick="this.closest('.modal-overlay').remove()" 
                        style="background: #ef4444; color: white; border: none; padding: 10px 20px; 
                               border-radius: 8px; cursor: pointer; font-weight: 600; transition: all 0.2s;"
                        onmouseover="this.style.background='#dc2626'"
                        onmouseout="this.style.background='#ef4444'">
                    <i class="fas fa-times"></i> Close
                </button>
            </div>
    `;
    
    // Display month-wise data
    Object.keys(groupedByMonth).sort().forEach(monthRange => {
        const entries = groupedByMonth[monthRange];
        const totalAmount = entries.reduce((sum, e) => sum + (e.amount || 0), 0);
        
        modalContent += `
            <div style="margin-bottom: 30px; border: 2px solid #fee2e2; border-radius: 12px; overflow: hidden;">
                <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 15px 20px; display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="color: white; margin: 0; font-size: 18px; display: flex; align-items: center; gap: 10px;">
                        <i class="fas fa-calendar-alt"></i>
                        ${monthRange}
                    </h3>
                    <span style="background: rgba(255,255,255,0.2); color: white; padding: 6px 12px; border-radius: 8px; font-weight: 600;">
                        Total: ₹${totalAmount.toFixed(2)} | Entries: ${entries.length}
                    </span>
                </div>
                <div style="overflow-x: auto;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead style="background: #fef2f2;">
                            <tr>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Date</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Client</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Project ID</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Project Name</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Type</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">From</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">To</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Mode</th>
                                <th style="padding: 12px; text-align: right; border-bottom: 2px solid #fee2e2; font-size: 13px;">Amount</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Rejected By</th>
                                <th style="padding: 12px; text-align: left; border-bottom: 2px solid #fee2e2; font-size: 13px;">Reason</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        
        entries.forEach(entry => {
            modalContent += `
                <tr style="border-bottom: 1px solid #fef2f2;">
                    <td style="padding: 12px; font-size: 13px;">${entry.date || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.client || '-'}</td>
                    <td style="padding: 12px; font-size: 13px; color: #3b82f6; font-weight: 600;">${entry.project_id || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.project_name || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">
                        <span style="background: #fee2e2; color: #991b1b; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 600;">
                            ${entry.project_type || '-'}
                        </span>
                    </td>
                    <td style="padding: 12px; font-size: 13px;">${entry.location_from || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${entry.location_to || '-'}</td>
                    <td style="padding: 12px; font-size: 13px;">${getTravelModeLabel(entry.travel_mode)}</td>
                    <td style="padding: 12px; text-align: right; font-weight: 700; color: #dc2626; font-size: 14px;">₹${entry.amount || 0}</td>
                    <td style="padding: 12px; font-size: 13px; color: #dc2626; font-weight: 600;">${entry.rejector_name || entry.rejected_by || '-'}</td>
                    <td style="padding: 12px; font-size: 12px; color: #dc2626; max-width: 200px;">
                        <div style="max-height: 60px; overflow-y: auto;">
                            ${entry.rejection_reason || '-'}
                        </div>
                    </td>
                </tr>
            `;
        });
        
        modalContent += `
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    });
    
    modalContent += `</div>`;
    
    modal.innerHTML = modalContent;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    // Close on overlay click
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            overlay.remove();
        }
    });
}

// Make it global
window.showRejectedEmployeeModal = showRejectedEmployeeModal;

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

// async function approveRejectedEmployee(employeeId) {
//     const token = localStorage.getItem('access_token');
    
//     try {
//         console.log("✅ Approving all rejected entries for:", employeeId);
        
//         const confirmed = await showConfirmPopup(
//             'Approve All Rejected Entries',
//             `Are you sure you want to approve all rejected entries for employee ${employeeId}?`,
//             'Yes, Approve All',
//             'Cancel'
//         );
        
//         if (!confirmed) {
//             return;
//         }
        
//         // Get all rejected entries for this employee
//         const employeeEntries = allRejectData.filter(e => e.employee_id === employeeId);
        
//         if (employeeEntries.length === 0) {
//             showErrorPopup('No rejected entries found');
//             return;
//         }
        
//         let approvedCount = 0;
        
//         // ✅ Approve each entry one by one
//         for (const entry of employeeEntries) {
//             const response = await fetch(`${API_URL}/api/ope/manager/approve-single`, {
//                 method: 'POST',
//                 headers: {
//                     'Authorization': `Bearer ${token}`,
//                     'Content-Type': 'application/json'
//                 },
//                 body: JSON.stringify({ 
//                     entry_id: entry._id,
//                     employee_id: employeeId
//                 })
//             });
            
//             if (response.ok) {
//                 approvedCount++;
//             }
//         }
        
//         if (approvedCount > 0) {
//             showSuccessPopup(`Approved ${approvedCount} rejected entries for employee ${employeeId}`);
            
//             // ✅ Reload reject data
//             const empCode = localStorage.getItem('employee_code');
//             await loadRejectData(token, empCode);
//         }
        
//     } catch (error) {
//         console.error('Approval error:', error);
//         showErrorPopup('Network error during approval');
//     }
// }

async function approveRejectedEmployee(employeeId) {
    const token = localStorage.getItem('access_token');
    const currentEmpCode = localStorage.getItem('employee_code');
    
    try {
        console.log("✅ Approving all rejected entries for:", employeeId);
        
        const confirmed = await showConfirmPopup(
            'Approve All Rejected Entries',
            `Are you sure you want to approve all rejected entries for employee ${employeeId}?`,
            'Yes, Approve All',
            'Cancel'
        );
        
        if (!confirmed) {
            return;
        }
        
        // Get all rejected entries for this employee
        const employeeEntries = allRejectData.filter(e => e.employee_id === employeeId);
        
        if (employeeEntries.length === 0) {
            showErrorPopup('No rejected entries found');
            return;
        }
        
        let approvedCount = 0;
        
        // ✅ CHECK IF USER IS HR
        const isHR = (currentEmpCode.toUpperCase() === "JHS729");
        
        if (isHR) {
            // ✅ HR BULK APPROVE
            const response = await fetch(`${API_URL}/api/ope/hr/approve/${employeeId}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
            
            if (response.ok) {
                const result = await response.json();
                showSuccessPopup(`HR approved ${result.approved_count} entries for employee ${employeeId}`);
                
                // Reload reject and approve data
                await loadRejectData(token, currentEmpCode);
                await loadApproveData(token, currentEmpCode);
            } else {
                const errorData = await response.json();
                showErrorPopup(errorData.detail || 'Approval failed');
            }
        } else {
            // ✅ MANAGER SINGLE-ENTRY APPROVE
            for (const entry of employeeEntries) {
                const response = await fetch(`${API_URL}/api/ope/manager/approve-single`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ 
                        entry_id: entry._id,
                        employee_id: employeeId
                    })
                });
                
                if (response.ok) {
                    approvedCount++;
                }
            }
            
            if (approvedCount > 0) {
                showSuccessPopup(`Approved ${approvedCount} rejected entries for employee ${employeeId}`);
                
                // Reload reject and approve data
                await loadRejectData(token, currentEmpCode);
                await loadApproveData(token, currentEmpCode);
            }
        }
        
    } catch (error) {
        console.error('Approval error:', error);
        showErrorPopup('Network error during approval');
    }
}

// Make it global
window.approveRejectedEmployee = approveRejectedEmployee;

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
      
      // ✅ Reload reject data to refresh list
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
// function toggleManagerButtons(isManager) {
//   const navPending = document.getElementById('navPending');
//   const navApprove = document.getElementById('navApprove');
//   const navReject = document.getElementById('navReject');
  
//   console.log("🔧 toggleManagerButtons called with isManager:", isManager);
  
//   if (isManager) {
//     console.log("👔 User is a manager - showing buttons");
//     if (navPending) {
//       navPending.style.display = 'flex';
//       console.log("✅ Pending button shown");
//     }
//     if (navApprove) {
//       navApprove.style.display = 'flex';
//       console.log("✅ Approve button shown");
//     }
//     if (navReject) {
//       navReject.style.display = 'flex';
//       console.log("✅ Reject button shown");
//     }
//   } else {
//     console.log("👤 User is an employee - hiding buttons");
//     if (navPending) navPending.style.display = 'none';
//     if (navApprove) navApprove.style.display = 'none';
//     if (navReject) navReject.style.display = 'none';
//   }
// }

// ============================================
// FIXED: toggleManagerButtons function
// ============================================

function toggleManagerButtons(isManager) {
  console.log("🔧 toggleManagerButtons called with isManager:", isManager);
  
  const navPending = document.getElementById('navPending');
  const navApprove = document.getElementById('navApprove');
  const navReject = document.getElementById('navReject');
  
  if (isManager) {
    console.log("👔 USER IS MANAGER - Showing manager buttons");
    
    if (navPending) {
      navPending.style.display = 'flex';
      navPending.classList.add('show');
      console.log("✅ Pending button shown");
    }
    
    if (navApprove) {
      navApprove.style.display = 'flex';
      navApprove.classList.add('show');
      console.log("✅ Approve button shown");
    }
    
    if (navReject) {
      navReject.style.display = 'flex';
      navReject.classList.add('show');
      console.log("✅ Reject button shown");
    }
  } else {
    console.log("👤 USER IS EMPLOYEE - Hiding manager buttons");
    
    if (navPending) {
      navPending.style.display = 'none';
      navPending.classList.remove('show');
      console.log("✅ Pending button hidden");
    }
    
    if (navApprove) {
      navApprove.style.display = 'none';
      navApprove.classList.remove('show');
      console.log("✅ Approve button hidden");
    }
    
    if (navReject) {
      navReject.style.display = 'none';
      navReject.classList.remove('show');
      console.log("✅ Reject button hidden");
    }
  }
}

// Make it globally accessible
window.toggleManagerButtons = toggleManagerButtons;

console.log("✅ Manager Buttons Toggle initialized!");

// Update checkUserRole to use isManager

async function checkUserRole() {
  try {
    const token = localStorage.getItem("access_token");
    const empCode = localStorage.getItem("employee_code");
    
    if (!token || !empCode) {
      console.log("❌ No token or empCode, skipping role check");
      return false;
    }
    
    console.log("🔍 Checking user role for:", empCode);
    
    // ✅ CHECK IF USER IS HR
    const isHR = (empCode.trim().toUpperCase() === "JHS729");
    
    if (isHR) {
      console.log("👔 User is HR - showing manager buttons");
      localStorage.setItem("is_manager", "true");
      localStorage.setItem("is_hr", "true");
      toggleManagerButtons(true);
      return true;
    }
    
    // ✅ CHECK IF USER IS REPORTING MANAGER
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
    localStorage.setItem("is_hr", "false");
    
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

// ✅ NEW: Edit amount in pending entry
async function editEntryAmount(entryId, employeeId, currentAmount) {
    const newAmount = await showAmountEditPopup(currentAmount);
    
    if (newAmount === null || newAmount === currentAmount) {
        return; // User cancelled or no change
    }
    
    if (newAmount <= 0) {
        showErrorPopup('Amount must be greater than 0');
        return;
    }
    
    const token = localStorage.getItem('access_token');
    
    try {
        console.log(`💰 Updating amount for entry ${entryId}: ${currentAmount} → ${newAmount}`);
        
        const response = await fetch(`${API_URL}/api/ope/manager/edit-amount`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                entry_id: entryId,
                employee_id: employeeId,
                new_amount: newAmount
            })
        });
        
        if (response.ok) {
            showSuccessPopup('Amount updated successfully!');
            
            // Reload the current section
            const empCode = localStorage.getItem('employee_code');
            const navPending = document.getElementById('navPending');
            const navApprove = document.getElementById('navApprove');
            const navReject = document.getElementById('navReject');
            
            if (navPending && navPending.classList.contains('active')) {
                await loadPendingData(token, empCode);
            } else if (navApprove && navApprove.classList.contains('active')) {
                await loadApproveData(token, empCode);
            } else if (navReject && navReject.classList.contains('active')) {
                await loadRejectData(token, empCode);
            }
        } else {
            const errorData = await response.json();
            showErrorPopup(errorData.detail || 'Failed to update amount');
        }
        
    } catch (error) {
        console.error('Error updating amount:', error);
        showErrorPopup('Network error');
    }
}

// ✅ NEW: Amount Edit Popup
function showAmountEditPopup(currentAmount) {
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
            max-width: 400px;
            width: 90%;
            animation: slideUp 0.3s ease;
        `;

        popup.innerHTML = `
            <div style="text-align: center; margin-bottom: 20px;">
                <div style="
                    width: 70px;
                    height: 70px;
                    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                    border-radius: 50%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0 auto 15px;
                ">
                    <i class="fas fa-rupee-sign" style="font-size: 30px; color: white;"></i>
                </div>
                <h2 style="font-size: 22px; color: #1f2937; margin-bottom: 8px; font-weight: 600;">Edit Amount</h2>
                <p style="color: #6b7280; font-size: 14px;">Current amount: ₹${currentAmount}</p>
            </div>
            
            <div style="margin-bottom: 20px;">
                <label style="display: block; font-weight: 600; margin-bottom: 8px; color: #374151;">New Amount (₹)</label>
                <input 
                    type="number" 
                    id="newAmountInput" 
                    value="${currentAmount}" 
                    min="0" 
                    step="0.01"
                    style="
                        width: 100%;
                        padding: 12px;
                        border: 2px solid #e5e7eb;
                        border-radius: 8px;
                        font-size: 16px;
                        font-weight: 600;
                        box-sizing: border-box;
                    "
                    autofocus
                />
            </div>
            
            <div style="display: flex; gap: 12px; justify-content: center;">
                <button id="saveAmountBtn" style="
                    padding: 12px 28px;
                    background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
                    color: white;
                    border: none;
                    border-radius: 10px;
                    font-size: 15px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s ease;
                    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
                ">
                    <i class="fas fa-check"></i> Update
                </button>
                <button id="cancelAmountBtn" style="
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

        const input = document.getElementById('newAmountInput');
        const saveBtn = document.getElementById('saveAmountBtn');
        const cancelBtn = document.getElementById('cancelAmountBtn');

        // Focus and select input
        setTimeout(() => {
            input.focus();
            input.select();
        }, 100);

        // Save button
        saveBtn.addEventListener('click', () => {
            const newAmount = parseFloat(input.value);
            document.body.removeChild(overlay);
            resolve(newAmount);
        });

        // Cancel button
        cancelBtn.addEventListener('click', () => {
            document.body.removeChild(overlay);
            resolve(null);
        });

        // Enter key
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                const newAmount = parseFloat(input.value);
                document.body.removeChild(overlay);
                resolve(newAmount);
            }
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

// Make it global
window.editEntryAmount = editEntryAmount;

// ✅ NEW: Edit Total Amount for entire month
async function editTotalAmount(employeeId, monthRange, currentTotal) {
    const newTotal = await showAmountEditPopup(currentTotal);
    
    if (newTotal === null || newTotal === currentTotal) {
        return;
    }
    
    if (newTotal <= 0) {
        showErrorPopup('Total amount must be greater than 0');
        return;
    }
    
    const token = localStorage.getItem('access_token');
    
    try {
        console.log(`💰 Updating total amount for ${employeeId} - ${monthRange}: ${currentTotal} → ${newTotal}`);
        
        const response = await fetch(`${API_URL}/api/ope/manager/edit-total-amount`, {
            method: 'PUT',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                employee_id: employeeId,
                month_range: monthRange,
                new_total: newTotal
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            showSuccessPopup(`Total amount updated successfully!\n\nOld Total: ₹${currentTotal}\nNew Total: ₹${newTotal}\nEntries adjusted: ${result.entries_updated}`);
            
            // Reload the current section
            const empCode = localStorage.getItem('employee_code');
            const navPending = document.getElementById('navPending');
            const navApprove = document.getElementById('navApprove');
            const navReject = document.getElementById('navReject');
            
            if (navPending && navPending.classList.contains('active')) {
                await loadPendingData(token, empCode);
            } else if (navApprove && navApprove.classList.contains('active')) {
                await loadApproveData(token, empCode);
            } else if (navReject && navReject.classList.contains('active')) {
                await loadRejectData(token, empCode);
            }
        } else {
            const errorData = await response.json();
            showErrorPopup(errorData.detail || 'Failed to update total amount');
        }
        
    } catch (error) {
        console.error('Error updating total amount:', error);
        showErrorPopup('Network error');
    }
}

// Make it global
window.editTotalAmount = editTotalAmount;

async function approveEmployee(employeeId) {
  const token = localStorage.getItem('access_token');
  const currentEmpCode = localStorage.getItem('employee_code');
  
  try {
    console.log("✅ Approving employee:", employeeId);
    
    const confirmed = await showConfirmPopup(
      'Approve All Entries',
      `Are you sure you want to approve all entries for ${employeeId}?`,
      'Yes, Approve',
      'Cancel'
    );
    
    if (!confirmed) {
      return;
    }
    
    // ✅ DETERMINE ENDPOINT BASED ON USER
    const isHR = (currentEmpCode.toUpperCase() === "JHS729");
    const endpoint = isHR 
      ? `${API_URL}/api/ope/hr/approve/${employeeId}`
      : `${API_URL}/api/ope/manager/approve/${employeeId}`;
    
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      }
    });
    
    if (response.ok) {
      const result = await response.json();
      showSuccessPopup(`Approved ${result.approved_count} entries for employee ${employeeId}`);
      
      const modals = document.querySelectorAll('.modal-overlay');
      modals.forEach(modal => modal.remove());
      
      await loadPendingData(token, currentEmpCode);
      
    } else {
      const errorData = await response.json();
      showErrorPopup(errorData.detail || 'Approval failed');
    }
    
  } catch (error) {
    console.error('Approval error:', error);
    showErrorPopup(`Network error: ${error.message}`);
  }
}


// async function rejectEmployee(employeeId) {
//   const token = localStorage.getItem('access_token');
  
//   try {
//     console.log("❌ Rejecting employee:", employeeId);
    
//     // ✅ Ask for rejection reason
//     const reason = await showRejectReasonPopup();
    
//     if (!reason) {
//       return; // User cancelled
//     }
    
//     const response = await fetch(`${API_URL}/api/ope/manager/reject/${employeeId}`, {
//       method: 'POST',
//       headers: {
//         'Authorization': `Bearer ${token}`,
//         'Content-Type': 'application/json'
//       },
//       body: JSON.stringify({ reason: reason })
//     });
    
//     if (response.ok) {
//       const result = await response.json();
//       showSuccessPopup(`Rejected ${result.rejected_count} entries for employee ${employeeId}`);
      
//       // Close modal if open
//       const modals = document.querySelectorAll('.modal-overlay');
//       modals.forEach(modal => modal.remove());
      
//       // Reload pending data
//       const empCode = localStorage.getItem('employee_code');
//       await loadPendingData(token, empCode);
      
//     } else {
//       const errorData = await response.json();
//       showErrorPopup(errorData.detail || 'Rejection failed');
//     }
    
//   } catch (error) {
//     console.error('Rejection error:', error);
//     showErrorPopup('Network error during rejection');
//   }
// }

// ✅ NEW: Rejection Reason Popup

// ✅ UPDATED: Reject with HR logic
async function rejectEmployee(employeeId) {
  const token = localStorage.getItem('access_token');
  const currentEmpCode = localStorage.getItem('employee_code');
  
  try {
    console.log("❌ Rejecting employee:", employeeId);
    
    const reason = await showRejectReasonPopup();
    
    if (!reason) {
      return;
    }
    
    // ✅ DETERMINE ENDPOINT BASED ON USER
    const isHR = (currentEmpCode.toUpperCase() === "JHS729");
    const endpoint = isHR 
      ? `${API_URL}/api/ope/hr/reject/${employeeId}`
      : `${API_URL}/api/ope/manager/reject/${employeeId}`;
    
    const response = await fetch(endpoint, {
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
      
      const modals = document.querySelectorAll('.modal-overlay');
      modals.forEach(modal => modal.remove());
      
      await loadPendingData(token, currentEmpCode);
      
    } else {
      const errorData = await response.json();
      showErrorPopup(errorData.detail || 'Rejection failed');
    }
    
  } catch (error) {
    console.error('Rejection error:', error);
    showErrorPopup('Network error during rejection');
  }
}

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

// ============================================
// STATUS SECTION - NEW IMPLEMENTATION
// ============================================
let allStatusData = [];

async function loadStatusData(token, empCode) {
    try {
        console.log("📊 Loading status data for:", empCode);
        
        document.getElementById('statusLoadingDiv').style.display = 'block';
        document.getElementById('statusTableSection').style.display = 'none';
        document.getElementById('statusNoDataDiv').style.display = 'none';

        const response = await fetch(`${API_URL}/api/ope/status/${empCode}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) {
            console.error("❌ Status API failed:", response.status);
            throw new Error('Failed to fetch status');
        }

        const data = await response.json();
        console.log("✅ Raw status response:", data);
        
        allStatusData = data.status_entries || [];

        console.log("✅ Status data loaded:", allStatusData.length);
        console.log("📦 Status entries:", allStatusData);

        if (allStatusData.length === 0) {
            console.log("📭 No status entries found - checking OPE_data...");
            showStatusNoData();
        } else {
            displayStatusTable(allStatusData);
        }
    } catch (error) {
        console.error('❌ Error loading status:', error);
        document.getElementById('statusLoadingDiv').style.display = 'none';
        showStatusNoData();
    }
}


function displayStatusTable(data) {
    console.log("🎨 Displaying status table");
    
    const tbody = document.getElementById('statusTableBody');
    if (!tbody) {
        console.error("❌ statusTableBody not found!");
        return;
    }

    tbody.innerHTML = '';

    if (!data || data.length === 0) {
        showStatusNoData();
        return;
    }

    // ✅ Display each payroll month as one row
    data.forEach((entry) => {
        const row = document.createElement('tr');
        
        const L1 = entry.L1 || {};
        const L2 = entry.L2 || {};
        const L3 = entry.L3 || {};
        const totalLevels = entry.total_levels || 2;
        const currentLevel = entry.current_level || 'L1';
        const overallStatus = entry.overall_status || 'pending';
        
        // Generate status tracker HTML with compact design
        let statusTrackerHTML = `<div class="approval-tracker">`;
        
        // L1
        const l1Class = L1.status ? 'approved' : (currentLevel === 'L1' ? 'pending' : 'inactive');
        statusTrackerHTML += `
            <div class="approval-level ${l1Class}">
                <i class="fas ${L1.status ? 'fa-check-circle' : (currentLevel === 'L1' ? 'fa-clock' : 'fa-circle')}"></i>
                <div class="level-info">
                    <div class="level-title">L1 - ${L1.level_name || 'Manager'}</div>
                    <div class="level-status">
                        ${L1.status ? '✓ ' + (L1.approver_name || 'Approved') : '⏳ Pending'}
                    </div>
                    ${L1.status && L1.approved_date ? `
                        <div class="level-date">
                            ${new Date(L1.approved_date).toLocaleDateString('en-IN', {day: '2-digit', month: 'short'})}
                        </div>
                    ` : ''}
                </div>
            </div>
            <i class="fas fa-arrow-right approval-arrow ${L1.status ? 'active' : 'inactive'}"></i>
        `;
        
        // L2
        const l2Class = L2.status ? 'approved' : (currentLevel === 'L2' ? 'pending' : 'inactive');
        statusTrackerHTML += `
            <div class="approval-level ${l2Class}">
                <i class="fas ${L2.status ? 'fa-check-circle' : (currentLevel === 'L2' ? 'fa-clock' : 'fa-circle')}"></i>
                <div class="level-info">
                    <div class="level-title">L2 - ${L2.level_name || 'Partner'}</div>
                    <div class="level-status">
                        ${L2.status ? '✓ ' + (L2.approver_name || 'Approved') : '⏳ Pending'}
                    </div>
                    ${L2.status && L2.approved_date ? `
                        <div class="level-date">
                            ${new Date(L2.approved_date).toLocaleDateString('en-IN', {day: '2-digit', month: 'short'})}
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
        
        // L3 (only if total_levels = 3)
        if (totalLevels === 3) {
            const l3Class = L3.status ? 'approved' : (currentLevel === 'L3' ? 'pending' : 'inactive');
            statusTrackerHTML += `
                <i class="fas fa-arrow-right approval-arrow ${L2.status ? 'active' : 'inactive'}"></i>
                <div class="approval-level ${l3Class}">
                    <i class="fas ${L3.status ? 'fa-check-circle' : (currentLevel === 'L3' ? 'fa-clock' : 'fa-circle')}"></i>
                    <div class="level-info">
                        <div class="level-title">L3 - ${L3.level_name || 'HR'}</div>
                        <div class="level-status">
                            ${L3.status ? '✓ ' + (L3.approver_name || 'Approved') : '⏳ Pending'}
                        </div>
                        ${L3.status && L3.approved_date ? `
                            <div class="level-date">
                                ${new Date(L3.approved_date).toLocaleDateString('en-IN', {day: '2-digit', month: 'short'})}
                            </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }
        
        statusTrackerHTML += `</div>`;
        
        row.innerHTML = `
            <td>${entry.payroll_month || '-'}</td>
            <td>₹${(entry.total_amount || 0).toFixed(2)}</td>
            <td>
                <div class="status-badge-container">
                    <span class="status-badge ${overallStatus === 'approved' ? 'completed' : 'pending'}">
                        ${overallStatus === 'approved' ? '✓ COMPLETED' : '⏳ IN PROGRESS'}
                    </span>
                    <div class="status-info">
                        Levels: <strong>${totalLevels}</strong> | 
                        Limit: <strong>₹${(entry.limit || 0).toFixed(0)}</strong>
                    </div>
                </div>
            </td>
            <td>
                ${statusTrackerHTML}
            </td>
        `;
        
        tbody.appendChild(row);
    });

    document.getElementById('statusLoadingDiv').style.display = 'none';
    document.getElementById('statusTableSection').style.display = 'block';
}

function generateStatusTracker(L1, L2, L3, currentLevel) {
    return `
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <!-- L1 - Reporting Manager -->
            <div style="
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 10px 14px;
                border-radius: 8px;
                background: ${L1.status ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : currentLevel === 'L1' ? '#fef3c7' : '#f1f5f9'};
                border: 2px solid ${L1.status ? '#059669' : currentLevel === 'L1' ? '#f59e0b' : '#e2e8f0'};
                min-width: 180px;
            ">
                <i class="fas ${L1.status ? 'fa-check-circle' : currentLevel === 'L1' ? 'fa-clock' : 'fa-circle'}" 
                   style="color: ${L1.status ? 'white' : currentLevel === 'L1' ? '#f59e0b' : '#94a3b8'}; font-size: 18px;"></i>
                <div>
                    <div style="
                        font-size: 11px;
                        font-weight: 700;
                        color: ${L1.status ? 'white' : '#475569'};
                        margin-bottom: 3px;
                        text-transform: uppercase;
                    ">
                        L1 - ${L1.level_name || 'Reporting Manager'}
                    </div>
                    <div style="
                        font-size: 10px;
                        font-weight: 600;
                        color: ${L1.status ? 'rgba(255,255,255,0.95)' : '#64748b'};
                    ">
                        ${L1.status ? '✓ Approved by ' + L1.approver_name : '⏳ Pending at ' + L1.approver_name}
                    </div>
                    ${L1.status && L1.approved_date ? `
                        <div style="
                            font-size: 9px;
                            color: ${L1.status ? 'rgba(255,255,255,0.85)' : '#94a3b8'};
                            margin-top: 2px;
                        ">
                            ${new Date(L1.approved_date).toLocaleDateString('en-IN', {day: '2-digit', month: 'short', year: 'numeric'})}
                        </div>
                    ` : ''}
                </div>
            </div>
            
            <!-- Arrow -->
            <i class="fas fa-arrow-right" style="color: ${L1.status ? '#10b981' : '#94a3b8'}; font-size: 16px;"></i>
            
            <!-- L2 - Partner -->
            <div style="
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 10px 14px;
                border-radius: 8px;
                background: ${L2.status ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : currentLevel === 'L2' ? '#fef3c7' : '#f1f5f9'};
                border: 2px solid ${L2.status ? '#059669' : currentLevel === 'L2' ? '#f59e0b' : '#e2e8f0'};
                min-width: 180px;
            ">
                <i class="fas ${L2.status ? 'fa-check-circle' : currentLevel === 'L2' ? 'fa-clock' : 'fa-circle'}" 
                   style="color: ${L2.status ? 'white' : currentLevel === 'L2' ? '#f59e0b' : '#94a3b8'}; font-size: 18px;"></i>
                <div>
                    <div style="
                        font-size: 11px;
                        font-weight: 700;
                        color: ${L2.status ? 'white' : '#475569'};
                        margin-bottom: 3px;
                        text-transform: uppercase;
                    ">
                        L2 - ${L2.level_name || 'Partner'}
                    </div>
                    <div style="
                        font-size: 10px;
                        font-weight: 600;
                        color: ${L2.status ? 'rgba(255,255,255,0.95)' : '#64748b'};
                    ">
                        ${L2.status ? '✓ Approved by ' + L2.approver_name : '⏳ Pending'}
                    </div>
                    ${L2.status && L2.approved_date ? `
                        <div style="
                            font-size: 9px;
                            color: ${L2.status ? 'rgba(255,255,255,0.85)' : '#94a3b8'};
                            margin-top: 2px;
                        ">
                            ${new Date(L2.approved_date).toLocaleDateString('en-IN', {day: '2-digit', month: 'short', year: 'numeric'})}
                        </div>
                    ` : ''}
                </div>
            </div>
            
            <!-- Arrow -->
            <i class="fas fa-arrow-right" style="color: ${L2.status ? '#10b981' : '#94a3b8'}; font-size: 16px;"></i>
            
            <!-- L3 - HR -->
            <div style="
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 10px 14px;
                border-radius: 8px;
                background: ${L3.status ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : currentLevel === 'L3' ? '#fef3c7' : '#f1f5f9'};
                border: 2px solid ${L3.status ? '#059669' : currentLevel === 'L3' ? '#f59e0b' : '#e2e8f0'};
                min-width: 180px;
            ">
                <i class="fas ${L3.status ? 'fa-check-circle' : currentLevel === 'L3' ? 'fa-clock' : 'fa-circle'}" 
                   style="color: ${L3.status ? 'white' : currentLevel === 'L3' ? '#f59e0b' : '#94a3b8'}; font-size: 18px;"></i>
                <div>
                    <div style="
                        font-size: 11px;
                        font-weight: 700;
                        color: ${L3.status ? 'white' : '#475569'};
                        margin-bottom: 3px;
                        text-transform: uppercase;
                    ">
                        L3 - ${L3.level_name || 'HR'}
                    </div>
                    <div style="
                        font-size: 10px;
                        font-weight: 600;
                        color: ${L3.status ? 'rgba(255,255,255,0.95)' : '#64748b'};
                    ">
                        ${L3.status ? '✓ Approved by ' + L3.approver_name : '⏳ Pending'}
                    </div>
                    ${L3.status && L3.approved_date ? `
                        <div style="
                            font-size: 9px;
                            color: ${L3.status ? 'rgba(255,255,255,0.85)' : '#94a3b8'};
                            margin-top: 2px;
                        ">
                            ${new Date(L3.approved_date).toLocaleDateString('en-IN', {day: '2-digit', month: 'short', year: 'numeric'})}
                        </div>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
}

function getStatusColor(status) {
    const colors = {
        'pending': 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
        'approved': 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
        'rejected': 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)'
    };
    return colors[status] || colors['pending'];
}

function getStatusLabel(status) {
    const labels = {
        'pending': 'IN PROGRESS',
        'approved': 'COMPLETED',
        'rejected': 'REJECTED'
    };
    return labels[status] || status.toUpperCase();
}

function showStatusNoData() {
    document.getElementById('statusLoadingDiv').style.display = 'none';
    document.getElementById('statusTableSection').style.display = 'none';
    document.getElementById('statusNoDataDiv').style.display = 'block';
}

function getOverallStatusColor(overallStatus, currentLevel) {
    if (overallStatus === 'approved') {
        return 'linear-gradient(135deg, #10b981 0%, #059669 100%)';
    }
    return 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)';
}

function getOverallStatusLabel(overallStatus, currentLevel, L1, L2, L3) {
    if (overallStatus === 'approved') {
        return '✓ COMPLETED';
    }
    
    // Show which level is currently pending
    if (L1.status && L2.status && !L3.status) {
        return '⏳ PENDING AT HR';
    } else if (L1.status && !L2.status) {
        return '⏳ PENDING AT PARTNER';
    } else {
        return '⏳ PENDING AT REPORTING MANAGER';
    }
}

// ============================================
// MOBILE MENU TOGGLE - FIXED VERSION
// ============================================

// Toggle mobile menu
function toggleMobileMenu() {
    const sidebar = document.querySelector('.sidebar');
    
    if (!sidebar) {
        console.error("❌ Sidebar not found!");
        return;
    }
    
    console.log("📱 Mobile menu toggle clicked");
    
    // Toggle the mobile-active class
    sidebar.classList.toggle('mobile-active');
    console.log("✅ Sidebar toggled - mobile-active:", sidebar.classList.contains('mobile-active'));
}

// Close mobile menu when clicking on navigation items
document.addEventListener('DOMContentLoaded', function() {
    const navItems = document.querySelectorAll('.nav-item');
    
    navItems.forEach(item => {
        item.addEventListener('click', function(e) {
            console.log("🔗 Navigation item clicked:", this.textContent.trim());
            
            const sidebar = document.querySelector('.sidebar');
            
            if (sidebar && sidebar.classList.contains('mobile-active')) {
                // Close mobile menu after clicking
                sidebar.classList.remove('mobile-active');
                console.log("✅ Mobile menu closed after nav click");
            }
        });
    });
    
    // Close menu when clicking outside sidebar
    document.addEventListener('click', function(e) {
        const sidebar = document.querySelector('.sidebar');
        const toggleBtn = document.querySelector('.mobile-menu-toggle');
        
        if (sidebar && toggleBtn && 
            !sidebar.contains(e.target) && 
            !toggleBtn.contains(e.target) &&
            sidebar.classList.contains('mobile-active')) {
            
            sidebar.classList.remove('mobile-active');
            console.log("✅ Mobile menu closed (clicked outside)");
        }
    });
    
    // Handle window resize - close menu on resize to desktop
    window.addEventListener('resize', function() {
        const sidebar = document.querySelector('.sidebar');
        
        if (window.innerWidth > 768 && sidebar && sidebar.classList.contains('mobile-active')) {
            sidebar.classList.remove('mobile-active');
            console.log("✅ Mobile menu closed (window resized to desktop)");
        }
    });
});

// Make it accessible globally
window.toggleMobileMenu = toggleMobileMenu;

console.log("✅ Mobile Menu Toggle initialized successfully!");