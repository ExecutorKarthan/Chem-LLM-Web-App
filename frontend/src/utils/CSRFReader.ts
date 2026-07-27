// Reads Django's CSRF token out of the 'csrftoken' cookie (set by the
// backend via ensure_csrf_cookie — see views.get_csrf_token) so it can
// be sent back as the X-CSRFToken header on POST requests. This is the
// standard manual cookie-parsing approach Django's own docs recommend
// when not using a cookie-reading library, since `document.cookie` is
// one opaque "name1=value1; name2=value2" string with no built-in
// per-cookie accessor.
//
// (Older comment here referenced a stale filename/typo and a .js
// extension that no longer match this file — removed as inaccurate.)
function getCSRFToken() {
  const name = 'csrftoken';
  let cookieValue = null;
  
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  
  return cookieValue;
}

export default getCSRFToken;