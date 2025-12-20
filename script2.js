let formCounter = 1;
let allHistoryData = [];
let originalRowData = {};

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
    <div style="
      width: 80px;
      height: 80px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 20px;
    ">
      <svg width="50" height="50" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
        <polyline points="20 6 9 17 4 12"></polyline>
      </svg>
    </div>
    <h2 style="font-size: 24px; color: #2d3748; margin-bottom: 15px;">Success!</h2>
    <p style="color: #718096; margin-bottom: 30px; font-size: 16px;">${message}</p>
    <button id="okBtn" style="
      padding: 12px 40px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      border: none;
      border-radius: 10px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.3s ease;
      box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
    ">OK</button>
  `;

  overlay.appendChild(popup);
  document.body.appendChild(overlay);

  document.getElementById('okBtn').addEventListener('click', function() {
    document.body.removeChild(overlay);
  });

  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) {
      document.body.removeChild(overlay);
    }
  });
}

// Error Popup Function
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
    <div style="
      width: 80px;
      height: 80px;
      background: linear-gradient(135deg, #f56565 0%, #e53e3e 100%);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 20px;
    ">
      <svg width="50" height="50" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
        <line x1="18" y1="6" x2="6" y2="18"></line>
        <line x1="6" y1="6" x2="18" y2="18"></line>
      </svg>
    </div>
    <h2 style="font-size: 24px; color: #2d3748; margin-bottom: 15px;">Error</h2>
    <p style="color: #718096; margin-bottom: 30px; font-size: 16px;">${message}</p>
    <button id="okBtn" style="
      padding: 12px 40px;
      background: linear-gradient(135deg, #f56565 0%, #e53e3e 100%);
      color: white;
      border: none;
      border-radius: 10px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.3s ease;
      box-shadow: 0 4px 15px rgba(245, 101, 101, 0.4);
    ">OK</button>
  `;

  overlay.appendChild(popup);
  document.body.appendChild(overlay);

  document.getElementById('okBtn').addEventListener('click', function() {
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

// MAIN INITIALIZATION
document.addEventListener("DOMContentLoaded", () => {
  // Set today's date
  const dateInput = document.getElementById('date');
  if (dateInput) dateInput.value = today;

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
      const res = await fetch(`http://localhost:8000/api/employee/${empCode}`, {
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

  // EXPAND FIRST FORM
  const firstForm = document.querySelector('.ope-form');
  if (firstForm) {
    firstForm.classList.add('expanded');
    const heading = firstForm.querySelector('h2');
    if (heading) heading.textContent = 'Entry #1';
    
    // ATTACH LISTENERS TO FIRST FORM
    attachFormListeners(firstForm, token, empCode);
  }

  // Initial button visibility check
  updateSubmitButtonVisibility();

  // Global click handler for expanding collapsed forms
  document.addEventListener('click', function(e) {
    const clickedForm = e.target.closest('.ope-form');
    
    if (clickedForm && clickedForm.classList.contains('collapsed')) {
      if (e.target.closest('input, select, textarea, button')) return;
      
      document.querySelectorAll('.ope-form').forEach(f => {
        f.classList.add('collapsed');
        f.classList.remove('expanded');
      });
      
      clickedForm.classList.remove('collapsed');
      clickedForm.classList.add('expanded');
    }
  });

  // MAKE addNewEntryForm AVAILABLE GLOBALLY
  window.addNewEntryForm = function() {
    addNewEntryFormWithToken(token, empCode);
  };
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
          
          const response = await fetch('http://localhost:8000/api/ope/submit', {
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
        const firstForm = document.querySelector('.ope-form');
        if (firstForm) {
          firstForm.classList.add('expanded');
          firstForm.classList.remove('collapsed');
          const heading = firstForm.querySelector('h2');
          if (heading) heading.textContent = 'Entry #1';
        }
        
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

// 1. Backend se History Data Load karne ka function
async function loadHistoryData(token, empCode) {
    try {
        // Loading show karo
        document.getElementById('loadingDiv').style.display = 'block';
        document.getElementById('historyTableSection').style.display = 'none';
        document.getElementById('noDataDiv').style.display = 'none';

        // API call
        const response = await fetch(`http://localhost:8000/api/ope/history/${empCode}`, {
            headers: { 
                'Authorization': `Bearer ${token}` 
            }
        });

        // Response check karo
        if (!response.ok) {
            throw new Error('Failed to fetch history');
        }

        const data = await response.json();
        allHistoryData = data.history || [];

        // Agar data nahi hai
        if (allHistoryData.length === 0) {
            showNoData();
            return;
        }

        // Month filter populate karo
        populateMonthFilter();
        
        // Table me data show karo
        displayHistoryTable(allHistoryData);
        
        // Loading hide karo
        hideLoading();

    } catch (error) {
        console.error('Error loading history:', error);
        showNoData();
    }
}

// 2. Month Filter Dropdown Populate karne ka function
function populateMonthFilter() {
    // Unique months nikaalo
    const monthSet = new Set();
    allHistoryData.forEach(item => {
        if (item.month_range) {
            monthSet.add(item.month_range);
        }
    });

    // Dropdown select karo
    const select = document.getElementById('monthRangeFilter');
    select.innerHTML = '<option value="">All Months</option>';

    // Sorted months add karo
    Array.from(monthSet).sort().forEach(month => {
        const option = document.createElement('option');
        option.value = month;
        option.textContent = month;
        select.appendChild(option);
    });

    // Filter change event
    select.addEventListener('change', function() {
        const selectedMonth = this.value;
        
        if (selectedMonth === '') {
            // All months show karo
            displayHistoryTable(allHistoryData);
        } else {
            // Selected month ka data filter karo
            const filteredData = allHistoryData.filter(item => 
                item.month_range === selectedMonth
            );
            displayHistoryTable(filteredData);
        }
    });
}

// 3. History Table me Data Display karne ka function
function displayHistoryTable(data) {
    const tbody = document.getElementById('historyTableBody');
    tbody.innerHTML = '';

    // Agar data empty hai
    if (data.length === 0) {
        showNoData();
        return;
    }

    // Har entry ke liye row banao
    data.forEach(entry => {
        const uniqueId = entry._id || `${entry.date}_${entry.client}_${entry.amount}_${Math.random()}`;
        const row = document.createElement('tr');
        row.dataset.entryId = entry._id;
        row.dataset.entryId = uniqueId;
        row.dataset.monthRange = entry.month_range;

        row.innerHTML = `
            <td>${entry.date || '-'}</td>
            <td>${entry.client || '-'}</td>
            <td>${entry.project_id || '-'}</td>
            <td>${entry.project_name || '-'}</td>
            <td>${entry.location_from || '-'}</td>
            <td>${entry.location_to || '-'}</td>
            <td>${getTravelModeLabel(entry.travel_mode)}</td>
            <td>₹${entry.amount || 0}</td>
            <td>${entry.remarks || 'NA'}</td>
            <td>
                ${entry.ticket_pdf 
                    ? `<button class="view-pdf-btn" onclick="viewPdf('${entry._id}')">
                        <i class="fas fa-file-pdf"></i> View
                       </button>` 
                    : '-'}
            </td>
            <td class="action-btns">
                <button class="edit-btn" onclick="editRow('${entry._id}')">
                    <i class="fas fa-edit"></i> Edit
                </button>
                <button class="delete-btn" onclick="deleteRow('${entry._id || 'dummy'}', '${entry.month_range}')">
    <i class="fas fa-trash"></i> Delete
  </button>
            </td>
        `;

        tbody.appendChild(row);
    });

    // Table show karo
    document.getElementById('historyTableSection').style.display = 'block';
    document.getElementById('noDataDiv').style.display = 'none';
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
        const response = await fetch(`http://localhost:8000/api/ope/update/${entryId}`, {
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
    console.log(`Deleting entry ID: ${entryId}, Month: ${monthRange}`); // Debug ke liye

    const response = await fetch(`http://localhost:8000/api/ope/delete/${entryId}`, {
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
    const opeSection = document.getElementById('opeSection');
    const historySection = document.getElementById('historySection');

    // OPE Section click
    if (navOPE) {
        navOPE.addEventListener('click', function() {
            opeSection.style.display = 'block';
            historySection.style.display = 'none';
            
            // Active styling
            navOPE.style.fontWeight = 'bold';
            navOPE.style.color = '#667eea';
            navHistory.style.fontWeight = 'normal';
            navHistory.style.color = '';
        });
    }

    // History Section click
    if (navHistory) {
        navHistory.addEventListener('click', async function() {
            opeSection.style.display = 'none';
            historySection.style.display = 'block';
            
            // Active styling
            navHistory.style.fontWeight = 'bold';
            navHistory.style.color = '#667eea';
            navOPE.style.fontWeight = 'normal';
            navOPE.style.color = '';

            // History data load karo
            const token = localStorage.getItem('access_token');
            const empCode = localStorage.getItem('employee_code');
            await loadHistoryData(token, empCode);
        });
    }
}

// 15. Success Popup Show karne ka function
function showSuccessPopup(message) {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0, 0, 0, 0.6); z-index: 99999;
        display: flex; align-items: center; justify-content: center;
    `;

    const popup = document.createElement('div');
    popup.style.cssText = `
        background: white; padding: 40px; border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        text-align: center; max-width: 400px;
    `;

    popup.innerHTML = `
        <div style="width: 80px; height: 80px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 50%; display: flex; align-items: center;
            justify-content: center; margin: 0 auto 20px;">
            <svg width="50" height="50" viewBox="0 0 24 24" fill="none" 
                stroke="white" stroke-width="3">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
        </div>
        <h2 style="font-size: 24px; color: #2d3748; margin-bottom: 15px;">Success!</h2>
        <p style="color: #718096; margin-bottom: 30px; font-size: 16px;">${message}</p>
        <button id="okBtn" style="padding: 12px 40px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white; border: none; border-radius: 10px;
            font-size: 16px; font-weight: 600; cursor: pointer;">OK</button>
    `;

    overlay.appendChild(popup);
    document.body.appendChild(overlay);

    document.getElementById('okBtn').addEventListener('click', () => {
        document.body.removeChild(overlay);
    });
}

// 16. Error Popup Show karne ka function
function showErrorPopup(message) {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0, 0, 0, 0.6); z-index: 99999;
        display: flex; align-items: center; justify-content: center;
    `;

    const popup = document.createElement('div');
    popup.style.cssText = `
        background: white; padding: 40px; border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        text-align: center; max-width: 400px;
    `;

    popup.innerHTML = `
        <div style="width: 80px; height: 80px;
            background: linear-gradient(135deg, #f56565 0%, #e53e3e 100%);
            border-radius: 50%; display: flex; align-items: center;
            justify-content: center; margin: 0 auto 20px;">
            <svg width="50" height="50" viewBox="0 0 24 24" fill="none" 
                stroke="white" stroke-width="3">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </div>
        <h2 style="font-size: 24px; color: #2d3748; margin-bottom: 15px;">Error</h2>
        <p style="color: #718096; margin-bottom: 30px; font-size: 16px;">${message}</p>
        <button id="okBtn" style="padding: 12px 40px;
            background: linear-gradient(135deg, #f56565 0%, #e53e3e 100%);
            color: white; border: none; border-radius: 10px;
            font-size: 16px; font-weight: 600; cursor: pointer;">OK</button>
    `;

    overlay.appendChild(popup);
    document.body.appendChild(overlay);

    document.getElementById('okBtn').addEventListener('click', () => {
        document.body.removeChild(overlay);
    });
}

// DOMContentLoaded me navigation setup karo
document.addEventListener('DOMContentLoaded', function() {
    setupNavigation();
});


let entryCounter = 0;
let copiedRowData = null;

// Initialize first row on page load
document.addEventListener('DOMContentLoaded', function() {
  addNewEntryRow();
});

// Add New Entry Row
function addNewEntryRow() {
  entryCounter++;
  const tbody = document.getElementById('entryTableBody');
  
  const row = document.createElement('tr');
  row.dataset.rowId = entryCounter;
  
  row.innerHTML = `
    <td><input type="date" name="date_${entryCounter}" value="${today}" required /></td>
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
    
  `;
  
  tbody.appendChild(row);
  
  // Scroll to new row
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

// Submit All Entries
// async function submitAllEntries() {
//   const token = localStorage.getItem('access_token');
//   const empCode = localStorage.getItem('employee_code');
//   const monthRange = document.getElementById('monthRange')?.value;
  
//   if (!monthRange) {
//     showErrorPopup('Please select month range first!');
//     return;
//   }
  
//   const tbody = document.getElementById('entryTableBody');
//   const rows = tbody.querySelectorAll('tr');
  
//   if (rows.length === 0) {
//     showErrorPopup('No entries to submit!');
//     return;
//   }
  
//   let successCount = 0;
//   let errorCount = 0;
//   let errors = [];
  
//   for (let i = 0; i < rows.length; i++) {
//     const row = rows[i];
//     const rowId = row.dataset.rowId;
    
//     const formData = new FormData();
    // formData.append('date', row.querySele