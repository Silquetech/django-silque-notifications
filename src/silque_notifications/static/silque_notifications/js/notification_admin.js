(function() {
  function post(url, data, success, fail) {
    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: new URLSearchParams(data)
    }).then(r => r.json()).then(success).catch(fail || function(){});
  }

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
  }

  function populateSelect(selectEl, values) {
    if (!selectEl) return;
    const current = Array.from(selectEl.selectedOptions).map(o => o.value);
    selectEl.innerHTML = '';
    // Add empty option first
    var emptyOpt = document.createElement('option');
    emptyOpt.value = '';
    emptyOpt.textContent = '--- Select ---';
    selectEl.appendChild(emptyOpt);
    
    values.forEach(function(v) {
      var opt = document.createElement('option');
      opt.value = v;
      opt.textContent = v;
      if (current.includes(v)) opt.selected = true;
      selectEl.appendChild(opt);
    });
  }

  function showConditionalFields(sendOn) {
    // Hide all conditional fields first - target the form-row containers
    const conditionalContainers = document.querySelectorAll('.form-row.field-value_change_field, .form-row.field-date_field, .form-row.field-alert_days');
    conditionalContainers.forEach(container => {
      container.style.display = 'none';
      container.classList.remove('show');
    });

    // Show relevant fields based on selection
    if (sendOn === 'V') {
      const valueContainer = document.querySelector('.form-row.field-value_change_field');
      if (valueContainer) {
        valueContainer.style.display = 'block';
        valueContainer.classList.add('show');
      }
    } else if (sendOn === 'B' || sendOn === 'A') {
      const dateContainer = document.querySelector('.form-row.field-date_field');
      const alertContainer = document.querySelector('.form-row.field-alert_days');
      
      if (dateContainer) {
        dateContainer.style.display = 'block';
        dateContainer.classList.add('show');
      }
      if (alertContainer) {
        alertContainer.style.display = 'block';
        alertContainer.classList.add('show');
      }
    }
  }

  function updateFields() {
    var sendOn = document.getElementById('id_send_alert_on');
    var modelSel = document.getElementById('id_model');
    if (!sendOn || !modelSel) return;

    var sel = sendOn.value;
    var modelVal = modelSel.value;
    
    
    
    // Show/hide conditional fields based on send_alert_on selection
    showConditionalFields(sel);
    
    if (!modelVal) return;

  var fieldsUrl = modelSel.getAttribute('data-fields-url') || '/get_model_fields/';
  var dateFieldsUrl = modelSel.getAttribute('data-date-fields-url') || '/get_model_date_fields/';

    if (sel === 'V') {
      
      post(fieldsUrl, { model: modelVal }, function(resp) {
        
        if (resp.status === 'S' && Array.isArray(resp.fields)) {
          populateSelect(document.getElementById('id_value_change_field'), resp.fields);
        }
      });
    } else if (sel === 'B' || sel === 'A') {
      
      post(dateFieldsUrl, { model: modelVal }, function(resp) {
        
        if (resp.status === 'S' && Array.isArray(resp.fields)) {
          populateSelect(document.getElementById('id_date_field'), resp.fields);
        }
      });
    }
  }

  function updateRelational() {
    var modelSel = document.getElementById('id_model');
    if (!modelSel || !modelSel.value) return;
    var modelVal = modelSel.value;
  var relUrl = modelSel.getAttribute('data-relational-url') || '/get_model_relational_recipients/';

    // Email suggestions
    post(relUrl, { model: modelVal, for_email: 'true' }, function(resp) {
      if (resp.status === 'S' && Array.isArray(resp.fields)) {
        populateSelect(document.getElementById('id_relational_email_selections'), resp.fields);
      } else if (resp.empty) {
        populateSelect(document.getElementById('id_relational_email_selections'), []);
      }
    });

    // Number suggestions
    post(relUrl, { model: modelVal, for_email: 'false' }, function(resp) {
      if (resp.status === 'S' && Array.isArray(resp.fields)) {
        populateSelect(document.getElementById('id_relational_number_selections'), resp.fields);
      } else if (resp.empty) {
        populateSelect(document.getElementById('id_relational_number_selections'), []);
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function() {
    var sendOn = document.getElementById('id_send_alert_on');
    var modelSel = document.getElementById('id_model');
    
    if (sendOn) {
      sendOn.addEventListener('change', updateFields);
      // Initialize field visibility on load
      showConditionalFields(sendOn.value);
    }
    
    if (modelSel) {
      modelSel.addEventListener('change', function() {
        updateFields();
        updateRelational();
      });
    }

    // Prefill on load when editing existing notifications
    updateFields();
    updateRelational();
  });
})();
