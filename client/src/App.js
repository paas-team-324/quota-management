import React from 'react';
import './App.css';
import Auth from './Auth';
import ResourceQuota from './ResourceQuota';
import { Container, Toolbar, AppBar, Typography, Select, Button } from '@material-ui/core';
import { Alert } from '@material-ui/lab';

class App extends React.Component {
    constructor () {
        super();

        this.state = {
            token: null,
            project_list: null,
            scheme: null,
            authenticated: false,
            project: null,
            scheme: {},
			output: {},
            output_valid: false,
			updating: false,
			update_button_text: "",
			update_button_text_available: "Update Quota",
			update_button_text_working: "Updating...",

			alerts: []
        };

        this.finishAuthentication = this.finishAuthentication.bind(this)
        this.edit = this.edit.bind(this)
        this.update = this.update.bind(this)
		this.closeAlert = this.closeAlert.bind(this)
    };

    finishAuthentication(token, project_list, scheme) {
        this.setState({
            token: token,
            project_list: project_list,
            scheme: scheme,
            authenticated: true,
            project: project_list[0],
			update_button_text: this.state.update_button_text_available
        })
    }

    edit(name, value) {

        let output = this.state.output

		// if not all keys are set - remove from final output
        if (Object.keys(value).length === Object.keys(this.state.scheme[name]).length) {
            output[name] = value
        } else {
            delete output[name]
        }

        this.setState({
            output: output,
            output_valid: (Object.keys(output).length === Object.keys(this.state.scheme).length ? true : false)
        })

    }

    update() {

		this.setState({
			update_button_text: this.state.update_button_text_working,
			updating: true
		})

		// prepare URL params
		let xhr_update_params = new URLSearchParams({
			token: this.state.token,
			project: this.state.project
		})

		// prepare quota update request
        let xhr_update = new XMLHttpRequest()
		xhr_update.open('PUT', window.ENV.BACKEND_ROUTE + "/quota?" + xhr_update_params.toString())

		// API response callback
		xhr_update.onreadystatechange = function () {
			if (xhr_update.readyState == XMLHttpRequest.DONE) {

				let alerts = this.state.alerts

				// push new alerts to alerts list
				alerts.push({
					"message": JSON.parse(xhr_update.responseText)["message"],
					"severity": (xhr_update.status == 200 ? "success" : "error")
				})

				// if more than three alerts - remove the oldest one
				if (alerts.length > 3) {
					alerts.shift()
				}

				this.setState({
					alerts: alerts,
					update_button_text: this.state.update_button_text_available,
					updating: false
				})

			}
		}.bind(this)

		xhr_update.send(JSON.stringify(this.state.output))
    }

	closeAlert(alert) {

		// get alert index
		let alerts = this.state.alerts
		let alertIndex = alerts.indexOf(alert)

		// delete alert by index
		if (alertIndex >= 0) {
			alerts.splice(alertIndex, 1)
		}

		// update alerts
		this.setState({
			alerts: alerts
		})
	}

    render () {
        return (
            <Container maxWidth="md">
                <AppBar color="primary">
                    <Toolbar style={{display: "grid"}}>
                        <Typography variant="h6" align="center">
                            Quota Management
                        </Typography>
                    </Toolbar>
                </AppBar>
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginTop: '15%'
                }}>
                    {this.state.authenticated ? (
                      	<Container style={{
							justifyContent: 'center',
						  }}>
							<Typography variant="h6" style={{ marginRight: "7px" }} gutterBottom>
								Project: 
								<Select
									native
									value={this.state.project}
									onChange={(event) => {
										this.setState({
											project: event.target.value
										})
									}}>
									{this.state.project_list.map(project =>
										<option key={project} value={project}>{project}</option>
									)}
								</Select>
							</Typography>
                        	{Object.keys(this.state.scheme).map(quota_object_name =>
                            	<ResourceQuota name={quota_object_name} fields={this.state.scheme[quota_object_name]} edit={this.edit}></ResourceQuota>)}
							<Button
								size="small"
								variant="contained"
								color="primary"
								component="span"
								disabled={!this.state.output_valid || this.state.updating}
								onClick={() => this.update()}>
								{this.state.update_button_text}
							</Button>
							{this.state.alerts.map(alert => 
								<Alert style={{ marginTop: "5px" }} severity={alert["severity"]} onClose={() => {this.closeAlert(alert)}}>{alert["message"]}</Alert>
							)}
                      	</Container>
                    ) : (
                      	<Auth token={this.state.token} project_list={this.state.project_list} scheme={this.state.scheme} finishAuthentication={this.finishAuthentication}></Auth>
                    )}
                </div>
            </Container>
        )
    }
}

export default App;