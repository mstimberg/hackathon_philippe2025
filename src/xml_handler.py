from lxml import etree
from time_utils import dotnet_ticks_to_rfc3339, rfc3339_to_dotnet_ticks

def parse_local_xml(path):
    """Parse XML appointments file and return list of events."""
    tree = etree.parse(path)
    root = tree.getroot()
    appointments = []
    for appointment in root.findall('Appointment'):
        id = appointment.find('ID').text
        start_ticks = appointment.find('Start').text
        end_ticks = appointment.find('End').text
        description = appointment.find('Description').text
        reminder = appointment.find('Reminder').text == 'True'
        appointments.append({
            'id': id,
            'start': dotnet_ticks_to_rfc3339(start_ticks),
            'end': dotnet_ticks_to_rfc3339(end_ticks),
            'description': description,
            'reminder': reminder
        })
    return appointments

def write_appointments_to_xml(appointments, xml_path):
    """Write appointments list to XML file."""
    # Create the root element
    root = etree.Element("AppointmentList")
    
    for appointment in appointments:
        # Create appointment element
        appt_elem = etree.SubElement(root, "Appointment")
        
        # Add child elements
        id_elem = etree.SubElement(appt_elem, "ID")
        id_elem.text = appointment['id']
        
        start_elem = etree.SubElement(appt_elem, "Start")
        # If it's a parsed appointment, convert back to ticks
        if 'start_ticks' in appointment:
            start_elem.text = appointment['start_ticks']
        else:
            # Convert from RFC3339 back to ticks
            start_elem.text = rfc3339_to_dotnet_ticks(appointment['start'])
        
        end_elem = etree.SubElement(appt_elem, "End")
        if 'end_ticks' in appointment:
            end_elem.text = appointment['end_ticks']
        else:
            end_elem.text = rfc3339_to_dotnet_ticks(appointment['end'])
        
        desc_elem = etree.SubElement(appt_elem, "Description")
        desc_elem.text = appointment['description']
        
        reminder_elem = etree.SubElement(appt_elem, "Reminder")
        reminder_elem.text = str(appointment['reminder'])
    
    # Write to file
    tree = etree.ElementTree(root)
    tree.write(xml_path, encoding='utf-8', xml_declaration=True, pretty_print=True) 