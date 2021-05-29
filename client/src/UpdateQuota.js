import React from 'react';
import Quota from './Quota'
import { Alert, AlertTitle } from '@material-ui/lab';
import { Grid, Typography, Select, Button, CircularProgress } from '@material-ui/core';

const update_button_idle = "Update Quota"
const update_button_working = "Updating..."

class UpdateQuota extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            loading: true,
            error: null,
            scheme: null,
            quota: {},
            current_quota: null,
            filled: true,
            project_list: null,
            project: null,
            update_button_text: update_button_idle,
            updating: false,
        };

        this.changeProject = this.changeProject.bind(this)
        this.update = this.update.bind(this)
    };

    changeProject(project) {

        this.setState({
            loading: true
        })

        // get current quota values
        this.props.request('GET', '/quota', { project: project }, {}, function(response, ok) {

            let responseJSON = JSON.parse(response)

            if (ok) {

                this.setState({
                    project: project,
                    current_quota: responseJSON,
                    quota: responseJSON,
                    loading: false
                })

            } else {

                this.props.addAlert(JSON.parse(response)["message"], "error")

                this.setState({
                    loading: false
                })

            }

        }.bind(this))
        
    }

    componentDidMount() {

        // request quota scheme
        this.props.request('GET', '/scheme', {}, {}, function(response, ok) {

            let responseJSON = JSON.parse(response)

            if (ok) {

                this.setState({
                    scheme: responseJSON
                })

                // request project list
                this.props.request('GET', '/projects', {}, {}, function(response, ok) {

                    let responseJSON = JSON.parse(response)

                    if (ok) {

                        if (responseJSON["projects"].length == 0) {

                            this.setState({
                                error: "there are no managed projects that exist in this cluster"
                            })
                            
                        } else {

                            // store list in state, then change to first project in list
                            this.setState({
                                project_list: responseJSON["projects"]
                            }, function() {
                                this.changeProject(this.state.project_list[0])
                            })

                        }

                    } else {
                        this.setState({
                            error: responseJSON["message"]
                        })
                    }

                }.bind(this))

            } else {
                this.setState({
                    error: responseJSON["message"]
                })
            }

        }.bind(this))

    }

    update() {

        // set button state
        this.setState({
            updating: true,
            update_button_text: update_button_working
        })

        // send update request
        this.props.request('PUT', '/quota', { project: this.state.project }, this.state.quota, function(response, ok) {

            // create appropriate alert
            this.props.addAlert(JSON.parse(response)["message"], ok ? "success" : "error")

            this.setState({
                updating: false,
                update_button_text: update_button_idle
            })

        }.bind(this))

    }

    render() {
        return (
            <div>
                {this.state.error == null ? (
                    <div>
                        {this.state.loading ? (
                            <div style={{display: 'flex', justifyContent:'center', alignItems:'center'}}>
                                <CircularProgress />
                            </div>
                            ) : (
                                <Grid container spacing={3}>
                                    <Grid item xs={9}>
                                        <Typography gutterBottom>
                                            <span style={{ marginRight: "1%" }}>Project:</span>
                                            <Select
                                                native
                                                value={this.state.project}
                                                onChange={(event) => {
                                                    this.changeProject(event.target.value)
                                                }}>
                                                {this.state.project_list.map(project =>
                                                    <option key={project} value={project}>{project}</option>
                                                )}
                                            </Select>
                                        </Typography>
                                    </Grid>
                                    <Grid item xs={3}>
                                        <Button
                                            size="small"
                                            variant="contained"
                                            color="primary"
                                            component="span"
                                            disabled={!this.state.filled || this.state.updating}
                                            fullWidth
                                            onClick={() => this.update()}>
                                            {this.state.update_button_text}
                                        </Button>
                                    </Grid>
                                    <Quota scheme={this.state.scheme} handleChange={(quota, filled) => {
                                        this.setState({
                                                quota: quota,
                                                filled: filled
                                        })
                                    }} current={this.state.current_quota}></Quota>
                                </Grid>
                            )}
                    </div>
                ) : (
                    <Alert severity="error">
                        <AlertTitle>Error</AlertTitle>
                        {this.state.error}
                    </Alert>
                )}
            </div>
        )
    }

}

export default UpdateQuota;