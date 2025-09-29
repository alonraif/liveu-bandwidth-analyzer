import re
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
import tarfile
import bz2
import tempfile
import os

class SessionAnalyzer:
    def __init__(self):
        self.session_patterns = {
            'session_id': r'SESSION ID:\s*(\d+)',
            'server_instance': r'(Boss\d+_\d+_Instance\d+)',
            'server_version': r'version:\s*([\d\.]+\.[A-Za-z]\d+\.[A-Za-z]\w+)',
            'unit_name': r'corecard\s+(\w+)\s+',
            'collector_address': r"destination':\s*\['([^']+)',\s*(\d+)\]",
            'ifb_address': r"ifbAddress':\s*\['([^']+)',\s*(\d+)\]",
            'stun_server': r"'host':\s*'([^']+)',.*?'port':\s*(\d+)",
            'video_port': r'listening to socket on port (\d+).*video',
            'audio_ports': r'listening to socket on port (\d+).*audio',
            'profile': r'Set probing profile to (\w+) profile',
            'spare_delay': r'Setting spare delay.*?(\d+\.\d+)\s*milliseconds',
            'active_links': r'returning (\d+) links.*?IDs:\s*\[(.*?)\]',
            'encryption': r'Encryption (enabled|disabled)',
            'state_transition': r'Entering state "([^"]+)" of state machine "([^"]+)"',
            'state_completion': r'Spent.*?seconds in state:\s*"([^"]+)".*?Moving to:\s*"([^"]+)"',
            'readiness_change': r"Got readiness:.*?'video':\s*'([^']+)'",
            'status_message': r"Got status message.*?'([^']+)'",
            'session_stop_gui': r'Stop command from the lu100 GUI',
            'session_stop_general': r'(?:stop|end|terminate|disconnect).*session',
            'session_disconnect': r'(?:disconnected|connection lost|stream ended)'
        }

    def analyze_file(self, file_path: str, start_datetime: Optional[str] = None, end_datetime: Optional[str] = None) -> Dict[str, Any]:
        """Analyze a log file for session information."""
        try:
            content = self._extract_file_content(file_path)
            sessions = self._parse_sessions(content)

            # Apply date/time filtering if provided
            if start_datetime or end_datetime:
                sessions = self._filter_sessions_by_datetime(sessions, start_datetime, end_datetime)

            return {
                'success': True,
                'total_sessions': len(sessions),
                'successful_sessions': len([s for s in sessions if s.get('final_status') == 'streaming']),
                'failed_sessions': len([s for s in sessions if s.get('final_status') not in ['streaming', 'collecting']]),
                'avg_setup_time': self._calculate_avg_setup_time(sessions),
                'avg_session_duration': self._calculate_avg_session_duration(sessions),
                'sessions': sessions
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'sessions': []
            }

    def _extract_file_content(self, file_path: str) -> str:
        """Extract content from various file formats."""
        content = ""

        if file_path.endswith('.tar.bz2') or file_path.endswith('.tar'):
            with tarfile.open(file_path, 'r:*') as tar:
                for member in tar.getmembers():
                    if member.isfile() and (member.name.endswith('.log') or 'messages' in member.name):
                        f = tar.extractfile(member)
                        if f:
                            file_content = f.read().decode('utf-8', errors='ignore')
                            content += file_content + "\n"

        elif file_path.endswith('.bz2'):
            with bz2.open(file_path, 'rt', encoding='utf-8', errors='ignore') as f:
                content = f.read()

        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

        return content

    def _parse_sessions(self, content: str) -> List[Dict[str, Any]]:
        """Parse session information from log content."""
        lines = content.split('\n')
        sessions = {}

        for line in lines:
            session_id = self._extract_session_id(line)

            if session_id:
                if session_id not in sessions:
                    sessions[session_id] = {
                        'session_id': session_id,
                        'state_timeline': [],
                        'network_config': {},
                        'streaming_config': {},
                        'start_time': None,
                        'end_time': None,
                        'session_duration': None,
                        'final_status': None,
                        'setup_duration': None
                    }

                session = sessions[session_id]
                timestamp = self._extract_timestamp(line)

                # Parse different types of information
                self._parse_connection_info(line, session)
                self._parse_network_config(line, session)
                self._parse_streaming_config(line, session)
                self._parse_state_info(line, session, timestamp)

        # Process sessions to calculate durations and final status
        processed_sessions = []
        for session in sessions.values():
            self._finalize_session(session)
            processed_sessions.append(session)

        return sorted(processed_sessions, key=lambda x: x.get('start_time') or '')

    def _extract_session_id(self, line: str) -> Optional[str]:
        """Extract session ID from log line."""
        match = re.search(self.session_patterns['session_id'], line)
        return match.group(1) if match else None

    def _extract_timestamp(self, line: str) -> Optional[str]:
        """Extract timestamp from log line."""
        timestamp_pattern = r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)'
        match = re.search(timestamp_pattern, line)
        return match.group(1) if match else None

    def _parse_connection_info(self, line: str, session: Dict[str, Any]):
        """Parse basic connection information."""
        # Unit name
        unit_match = re.search(self.session_patterns['unit_name'], line)
        if unit_match and not session.get('unit_name'):
            session['unit_name'] = unit_match.group(1)

        # Server instance
        server_match = re.search(self.session_patterns['server_instance'], line)
        if server_match and not session.get('server_instance'):
            session['server_instance'] = server_match.group(1)

        # Server version
        version_match = re.search(self.session_patterns['server_version'], line)
        if version_match and not session.get('server_version'):
            session['server_version'] = version_match.group(1)

    def _parse_network_config(self, line: str, session: Dict[str, Any]):
        """Parse network configuration details."""
        network_config = session['network_config']

        # Collector address
        collector_match = re.search(self.session_patterns['collector_address'], line)
        if collector_match:
            network_config['collector_address'] = f"{collector_match.group(1)}:{collector_match.group(2)}"

        # IFB address
        ifb_match = re.search(self.session_patterns['ifb_address'], line)
        if ifb_match:
            network_config['ifb_address'] = f"{ifb_match.group(1)}:{ifb_match.group(2)}"

        # STUN server
        stun_match = re.search(self.session_patterns['stun_server'], line)
        if stun_match:
            network_config['stun_server'] = f"{stun_match.group(1)}:{stun_match.group(2)}"

        # Video port
        video_port_match = re.search(self.session_patterns['video_port'], line)
        if video_port_match:
            network_config['video_port'] = video_port_match.group(1)

        # Audio ports
        audio_port_match = re.search(self.session_patterns['audio_ports'], line)
        if audio_port_match:
            if 'audio_ports' not in network_config:
                network_config['audio_ports'] = []
            network_config['audio_ports'].append(audio_port_match.group(1))

    def _parse_streaming_config(self, line: str, session: Dict[str, Any]):
        """Parse streaming configuration details."""
        streaming_config = session['streaming_config']

        # Profile
        profile_match = re.search(self.session_patterns['profile'], line)
        if profile_match:
            streaming_config['profile'] = profile_match.group(1)

        # Spare delay
        delay_match = re.search(self.session_patterns['spare_delay'], line)
        if delay_match:
            streaming_config['spare_delay'] = f"{delay_match.group(1)}ms"

        # Active links
        links_match = re.search(self.session_patterns['active_links'], line)
        if links_match:
            streaming_config['active_links'] = links_match.group(1)

        # Encryption
        encryption_match = re.search(self.session_patterns['encryption'], line)
        if encryption_match:
            streaming_config['encryption'] = encryption_match.group(1) == 'enabled'

    def _parse_state_info(self, line: str, session: Dict[str, Any], timestamp: Optional[str]):
        """Parse state transition and status information."""
        if not timestamp:
            return

        # State transitions
        state_match = re.search(self.session_patterns['state_transition'], line)
        if state_match:
            state_name = state_match.group(1)
            session['state_timeline'].append({
                'state': state_name,
                'timestamp': timestamp,
                'type': 'transition'
            })

            if not session['start_time']:
                session['start_time'] = timestamp

        # Readiness changes
        readiness_match = re.search(self.session_patterns['readiness_change'], line)
        if readiness_match:
            status = readiness_match.group(1)
            session['state_timeline'].append({
                'state': f"Video: {status}",
                'timestamp': timestamp,
                'type': 'readiness'
            })
            session['final_status'] = status

        # Status messages
        status_match = re.search(self.session_patterns['status_message'], line)
        if status_match:
            status = status_match.group(1)
            session['state_timeline'].append({
                'state': f"Status: {status}",
                'timestamp': timestamp,
                'type': 'status'
            })
            if status in ['collecting', 'streaming']:
                session['final_status'] = status

        # Session stop/end detection
        stop_gui_match = re.search(self.session_patterns['session_stop_gui'], line, re.IGNORECASE)
        stop_general_match = re.search(self.session_patterns['session_stop_general'], line, re.IGNORECASE)
        disconnect_match = re.search(self.session_patterns['session_disconnect'], line, re.IGNORECASE)

        if stop_gui_match or stop_general_match or disconnect_match:
            session['state_timeline'].append({
                'state': 'Session Stopped',
                'timestamp': timestamp,
                'type': 'end'
            })
            if not session['end_time']:
                session['end_time'] = timestamp

    def _finalize_session(self, session: Dict[str, Any]):
        """Calculate durations and finalize session data."""
        if not session['state_timeline']:
            return

        # Sort timeline by timestamp
        session['state_timeline'].sort(key=lambda x: x['timestamp'])

        # Calculate durations between states
        for i in range(len(session['state_timeline']) - 1):
            current = session['state_timeline'][i]
            next_item = session['state_timeline'][i + 1]

            try:
                current_time = datetime.fromisoformat(current['timestamp'].replace('Z', '+00:00'))
                next_time = datetime.fromisoformat(next_item['timestamp'].replace('Z', '+00:00'))
                duration = (next_time - current_time).total_seconds()
                current['duration'] = duration
            except:
                pass

        # Calculate total setup duration
        if session['start_time'] and session['final_status'] == 'streaming':
            try:
                start_time = datetime.fromisoformat(session['start_time'].replace('Z', '+00:00'))
                streaming_states = [s for s in session['state_timeline'] if 'streaming' in s.get('state', '').lower()]
                if streaming_states:
                    streaming_time = datetime.fromisoformat(streaming_states[0]['timestamp'].replace('Z', '+00:00'))
                    session['setup_duration'] = (streaming_time - start_time).total_seconds()
            except:
                pass

        # Calculate total session duration
        if session['start_time']:
            try:
                start_time = datetime.fromisoformat(session['start_time'].replace('Z', '+00:00'))

                # Use explicit end_time if available, otherwise use last timeline entry
                end_time_str = session['end_time']
                if not end_time_str and session['state_timeline']:
                    end_time_str = session['state_timeline'][-1]['timestamp']

                if end_time_str:
                    end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                    session['session_duration'] = (end_time - start_time).total_seconds()
            except:
                pass

    def _calculate_avg_setup_time(self, sessions: List[Dict[str, Any]]) -> Optional[float]:
        """Calculate average setup time for successful sessions."""
        durations = [s.get('setup_duration') for s in sessions if s.get('setup_duration')]
        return sum(durations) / len(durations) if durations else None

    def _calculate_avg_session_duration(self, sessions: List[Dict[str, Any]]) -> Optional[float]:
        """Calculate average total session duration."""
        durations = [s.get('session_duration') for s in sessions if s.get('session_duration')]
        return sum(durations) / len(durations) if durations else None

    def _filter_sessions_by_datetime(self, sessions: List[Dict[str, Any]], start_datetime: Optional[str] = None, end_datetime: Optional[str] = None) -> List[Dict[str, Any]]:
        """Filter sessions by date/time range."""
        if not start_datetime and not end_datetime:
            return sessions

        filtered_sessions = []

        for session in sessions:
            session_start = session.get('start_time')
            if not session_start:
                continue

            try:
                # Parse session start time
                session_dt = datetime.fromisoformat(session_start.replace('Z', '+00:00'))

                # Check start datetime filter
                if start_datetime:
                    start_dt = datetime.fromisoformat(start_datetime.replace(' ', 'T'))
                    if session_dt < start_dt:
                        continue

                # Check end datetime filter
                if end_datetime:
                    end_dt = datetime.fromisoformat(end_datetime.replace(' ', 'T'))
                    if session_dt > end_dt:
                        continue

                filtered_sessions.append(session)

            except Exception:
                # If we can't parse the datetime, include the session to be safe
                filtered_sessions.append(session)

        return filtered_sessions