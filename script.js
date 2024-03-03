function updateTime() {
  const daysOfWeek = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const now = new Date();
  let hours = now.getHours();
  const amPm = hours >= 12 ? 'PM' : 'AM';
  hours = hours % 12 || 12; // Convert to 12-hour format
  const minutes = now.getMinutes().toString().padStart(2, '0');
  const seconds = now.getSeconds().toString().padStart(2, '0');
  const date = now.getDate().toString().padStart(2, '0');
  const month = (now.getMonth() + 1).toString().padStart(2, '0');
  const year = now.getFullYear().toString();
  const dayOfWeek = daysOfWeek[now.getDay()];

  document.getElementById('time').textContent = `${hours}:${minutes}:${seconds} ${amPm} - ${dayOfWeek}, ${date}/${month}/${year}`;
}

setInterval(updateTime, 1000);
