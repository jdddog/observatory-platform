
output "private_ip_address" {
  value = google_compute_address.vm_private_ip.address
  description = "The private IP address of the virtual machine."
}