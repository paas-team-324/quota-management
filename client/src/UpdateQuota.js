import React from 'react';
import Quota from './Quota'
import { Alert, AlertTitle } from '@material-ui/lab';
import { Grid, Typography, Select, Button, CircularProgress } from '@material-ui/core';

const update_button_idle = "Edit"
const update_button_working = "Editing..."

class UpdateQuota extends React.Component {

    constructor(props) {
        super(props);

        this.state = {
            init_loading: true,
            init_error: null,
            project_loading: true,
            project_error: null,
            quota: {},
            current_quota: null,
            filled: false,
            project_list: [],
            project: null,
            update_button_text: update_button_idle,
            updating: false,
        };

        this.changeProject = this.changeProject.bind(this)
        this.update = this.update.bind(this)
    };

    componentDidUpdate(prevProps) {

        // remount component on cluster change
        if (this.props.cluster != prevProps.cluster) {

            this.setState({
                init_loading: true,
                init_error: null
            }, function() {
                this.componentDidMount()
            }.bind(this))

        }
    }

    changeProject(project) {

        this.setState({
            project: project,
            project_loading: true,
            project_error: null
        })

        // get current quota values
        this.props.request('GET', '/quota', { project: project }, {}, function(response, ok) {

            let responseJSON = JSON.parse(response)

            if (ok) {

                this.setState({
                    current_quota: responseJSON,
                    quota: responseJSON,
                    project_loading: false
                })

            } else {

                this.setState({
                    project_loading: false,
                    project_error: JSON.parse(response)["message"]
                })

            }

        }.bind(this))
        
    }

    componentDidMount() {

        // request project list
        this.props.request('GET', '/projects', {}, {}, function(response, ok) {

            let responseJSON = JSON.parse(response)

            if (ok) {

                if (responseJSON["projects"].length == 0) {

                    this.setState({
                        init_error: "There are no managed projects that exist in this cluster"
                    })
                    
                } else {

                    // store list in state, then change to first project in list
                    this.setState({
                        project_list: responseJSON["projects"],
                        init_loading: false
                    }, function() {
                        this.changeProject(this.state.project_list[0])
                    })

                }

            } else {
                this.setState({
                    init_error: responseJSON["message"]
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
                {this.state.init_error == null ? (
                    <div>
                        {this.state.init_loading ? (
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
                                            disabled={!this.state.filled || this.state.updating || this.state.project_loading || this.state.project_error != null}
                                            fullWidth
                                            onClick={() => this.update()}>
                                            {this.state.update_button_text}
                                        </Button>
                                    </Grid>
                                    {this.state.project_error == null ? (

                                            this.state.project_loading ? (

                                                <Grid item xs={12}>
                                                    <div style={{display: 'flex', justifyContent:'center', alignItems:'center'}}>
                                                        <CircularProgress />
                                                    </div>
                                                </Grid>

                                            ) : (

                                                <Quota request={this.props.request} handleChange={(quota, filled) => {
                                                    this.setState({
                                                            quota: quota,
                                                            filled: filled
                                                    })
                                                }} handleError={(error) => {
                                                    this.setState({
                                                        init_error: error
                                                    })
                                                }} current={this.state.current_quota} validator={this.props.validator} setWidth={this.props.setWidth}></Quota>

                                            )

                                    ) : (
                                        <Grid item xs={12}>
                                            <Alert severity="error">
                                                <AlertTitle>Error</AlertTitle>
                                                {this.state.project_error}
                                            </Alert>
                                        </Grid>
                                    )}
                                </Grid>
                            )}
                    </div>
                ) : (
                    <Alert severity="error">
                        <AlertTitle>Error</AlertTitle>
                        {this.state.init_error}
                    </Alert>
                )}
            </div>
        )
    }

}

export default UpdateQuota;