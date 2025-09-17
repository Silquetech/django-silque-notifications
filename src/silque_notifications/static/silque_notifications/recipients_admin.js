(function(){
  // Fetch suggestions using model_hint from URL and populate by_docfield when it's a select.
  function ready(fn){ if(document.readyState!=='loading'){fn()} else {document.addEventListener('DOMContentLoaded',fn)} }

  function post(url, data, cb){
    var csrf = document.querySelector('[name=csrfmiddlewaretoken]');
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': csrf ? csrf.value : '' },
      body: new URLSearchParams(data)
    }).then(r=>r.json()).then(cb).catch(()=>{});
  }

  function getUrlParam(name){
    var m = new RegExp('[?&]'+name+'=([^&#]*)').exec(window.location.search);
    return m ? decodeURIComponent(m[1].replace(/\+/g, ' ')) : '';
  }

  ready(function(){
    var byDoc = document.getElementById('id_by_docfield');
    if(!byDoc) return;
    var modelHint = getUrlParam('model_hint');
    if(!modelHint) return; // nothing to do
  var relUrl = (byDoc.getAttribute('data-relational-url')) || '/get_model_relational_recipients/';

    function populateSelect(selectEl, values){
      if(!selectEl || selectEl.tagName !== 'SELECT') return;
      var current = selectEl.value;
      selectEl.innerHTML = '';
      var empty = document.createElement('option');
      empty.value = '';
      empty.textContent = '--- Select ---';
      selectEl.appendChild(empty);
      (values||[]).forEach(function(v){ var o=document.createElement('option'); o.value=v.split(' ~ ')[0]; o.textContent=v; if(o.value===current) o.selected=true; selectEl.appendChild(o); });
    }

  var for_email = (document.getElementById('id_by_email') !== null).toString();
  post(relUrl, { model: modelHint, for_email: for_email }, function(resp){
      if(resp && resp.status==='S' && Array.isArray(resp.fields)){
        populateSelect(byDoc, resp.fields);
      }
    });
  });
})();
