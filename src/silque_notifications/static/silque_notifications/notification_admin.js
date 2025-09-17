(function(){
  // Add "Create via lookup" buttons next to M2M widgets, passing model_hint to popup
  function ready(fn){ if(document.readyState!=='loading'){fn()} else {document.addEventListener('DOMContentLoaded',fn)} }

  ready(function(){
    var modelVal = (document.getElementById('id_model')||{}).value || '';
    function applyModelHintToAnchor(a){
      if(!a || !a.href) return;
      var isEmail = a.href.indexOf('/admin/silque_notifications/emailrecipient/add/') !== -1;
      var isNumber = a.href.indexOf('/admin/silque_notifications/numberrecipient/add/') !== -1;
      if(!(isEmail||isNumber)) return;
      var base = a.href.split('?')[0];
      var qs = [];
      if(modelVal) qs.push('model_hint=' + encodeURIComponent(modelVal));
      qs.push('_popup=1');
      a.href = base + (qs.length ? ('?' + qs.join('&')) : '');
    }
    function attach(buttonText, m2mFieldId, addUrl){
      var box = document.getElementById(m2mFieldId);
      if(!box) return;
      var btn = document.createElement('a');
      var qs = [];
      if(modelVal) qs.push('model_hint=' + encodeURIComponent(modelVal));
      qs.push('_popup=1');
      btn.href = addUrl + (qs.length ? ('?' + qs.join('&')) : '');
      btn.className = 'button';
      btn.textContent = buttonText;
      btn.style.margin = '5px 0 0 0';
      // open in popup like admin's related widget
      btn.addEventListener('click', function(e){
        e.preventDefault();
        var url = btn.href;
        if(window.showAddAnotherPopup){
          window.showAddAnotherPopup({href: url});
        } else {
          var w = window.open(url, '_blank', 'width=900,height=700');
          if(w){ w.focus(); }
        }
      });
      // Place near the M2M filter widget container (field container)
      var container = box.closest('.form-row, .fieldBox, .form-group') || box.parentElement;
      container && container.appendChild(btn);
    }

    attach('Add EmailRecipient via lookup', 'id_email_recipients_from', '/admin/silque_notifications/emailrecipient/add/');
    attach('Add NumberRecipient via lookup', 'id_number_recipients_from', '/admin/silque_notifications/numberrecipient/add/');

    // Also adjust default Django related add icons if present
    document.querySelectorAll('a.add-another, a.related-widget-wrapper-link').forEach(function(a){
      applyModelHintToAnchor(a);
    });

    // Update links when model changes
    var modelSel = document.getElementById('id_model');
    if(modelSel){
      modelSel.addEventListener('change', function(){
    modelVal = modelSel.value || '';
        document.querySelectorAll('a.button').forEach(function(a){
          if(a.href.includes('/emailrecipient/add/') || a.href.includes('/numberrecipient/add/')){
      var base = a.href.split('?')[0];
      var qs = [];
      if(modelVal) qs.push('model_hint=' + encodeURIComponent(modelVal));
      qs.push('_popup=1');
      a.href = base + (qs.length ? ('?' + qs.join('&')) : '');
          }
        });
        document.querySelectorAll('a.add-another, a.related-widget-wrapper-link').forEach(function(a){
          applyModelHintToAnchor(a);
        });
      });
    }
  });
})();
